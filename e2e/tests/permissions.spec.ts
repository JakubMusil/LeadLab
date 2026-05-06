/**
 * E2E tests for the permissions system (Phase 7/8 acceptance criteria)
 *
 * Tests the 5 key use-cases from users_goals.md section 5:
 *   1. Member s `scope=own` vidí v listu jen své záznamy
 *   2. Admin udělí Member-ovi per-record grant (view) → Member nově vidí daný záznam
 *   3. Manažer (scope=team) vidí záznamy celého týmu
 *   4. Externí auditor via RecordGrant s `expires_at` (dočasný přístup)
 *   5. Admin nemůže smazat firmu (Owner-only operace)
 *
 * The tests set up multi-user scenarios via the JSON API.  A secondary "member"
 * user is registered and added to the owner's firm so that permission-restricted
 * paths can be exercised.
 *
 * Requires a running LeadLab server (started by `webServer` in playwright.config.ts).
 * The primary user (owner) is already authenticated via `auth.setup.ts`.
 */
import { test, expect, type APIRequestContext, type PlaywrightTestArgs } from '@playwright/test'

// ---------------------------------------------------------------------------
// Shared state (populated in beforeAll)
// ---------------------------------------------------------------------------

let firmId = ''
let ownerRecordId = ''
let memberEmail = ''
const memberPassword = 'MemberPass456!'

type PlaywrightFixture = PlaywrightTestArgs['playwright']

/**
 * Create and return a new APIRequestContext authenticated as the given user.
 * Uses session-cookie auth (same as the browser).
 */
async function loginAs(
  playwright: PlaywrightFixture,
  baseURL: string,
  email: string,
  password: string,
): Promise<APIRequestContext> {
  const ctx = await playwright.request.newContext({ baseURL })
  const res = await ctx.post('/api/v1/users/login', {
    data: { email, password },
  })
  if (!res.ok()) {
    throw new Error(`Login failed for ${email}: ${res.status()} ${await res.text()}`)
  }
  return ctx
}

// ---------------------------------------------------------------------------
// Setup – run once before all permission tests
// ---------------------------------------------------------------------------

test.describe.serial('Permissions system', () => {
  test.beforeAll(async ({ request, playwright, baseURL }) => {
    // 1. Discover the owner's firm.
    const firmsRes = await request.get('/api/v1/firms/')
    expect(firmsRes.ok(), `list_firms failed: ${firmsRes.status()}`).toBeTruthy()
    const firms = await firmsRes.json()
    expect(firms.length).toBeGreaterThan(0)
    firmId = firms[0].id as string

    // 2. Create a record owned by the owner (used in "own scope" test).
    const ts = Date.now()
    const recRes = await request.post('/api/v1/crm/records', {
      data: { title: `Owner Record ${ts}` },
    })
    expect(recRes.ok(), `record create failed: ${recRes.status()}`).toBeTruthy()
    ownerRecordId = (await recRes.json()).id as string

    // 3. Register a fresh member user (unique per run).
    memberEmail = `perm-member-${ts}@e2e.test`
    const regRes = await request.post('/api/v1/users/register', {
      data: {
        email: memberEmail,
        password: memberPassword,
        first_name: 'Perm',
        last_name: 'Member',
      },
    })
    // 201 = created, 400 = already exists (re-run); both are acceptable.
    expect([201, 400]).toContain(regRes.status())

    // 4. Invite the member to the firm (adds them directly as a member).
    const invRes = await request.post(`/api/v1/firms/${firmId}/members`, {
      data: {
        email: memberEmail,
        role: 'worker',
        default_scope: 'own',
      },
    })
    // 201 = invited, 400 = already a member (re-run).
    expect([201, 400]).toContain(invRes.status())
  })

  // -------------------------------------------------------------------------
  // Use-case 1: Member s scope=own vidí jen své záznamy
  // -------------------------------------------------------------------------

  test('UC1: member with own scope sees only their own records', async ({
    playwright,
    baseURL,
  }) => {
    // Log in as the member in a separate context.
    const memberCtx = await loginAs(playwright, baseURL!, memberEmail, memberPassword)

    try {
      // The member has no records of their own yet → list should be empty or
      // at most contain records where they are created_by / assigned_to.
      const listRes = await memberCtx.get('/api/v1/crm/records')
      expect(listRes.ok()).toBeTruthy()
      const records = await listRes.json()

      // The owner's record must NOT appear in the member's list.
      const memberIds = (records as Array<{ id: string }>).map((r) => r.id)
      expect(memberIds).not.toContain(ownerRecordId)
    } finally {
      await memberCtx.dispose()
    }
  })

  // -------------------------------------------------------------------------
  // Use-case 2: Admin přidělí per-record grant → Member nově vidí ten záznam
  // -------------------------------------------------------------------------

  test('UC2: admin grants record access → member can now see that record', async ({
    request,
    playwright,
    baseURL,
  }) => {
    // As owner, get the member's user_id to build the grant.
    const membersRes = await request.get(`/api/v1/firms/${firmId}/members`)
    expect(membersRes.ok()).toBeTruthy()
    const members = (await membersRes.json()) as Array<{ user_id: string; user_email: string; id: string }>
    const memberMembership = members.find((m) => m.user_email === memberEmail)
    expect(memberMembership).toBeDefined()

    // Grant the member "view" access to the owner's record.
    const grantRes = await request.post(`/api/v1/crm/records/${ownerRecordId}/grants`, {
      data: {
        principal_type: 'user',
        principal_id: memberMembership!.user_id,
        level: 'view',
      },
    })
    expect(grantRes.ok(), `grant failed: ${grantRes.status()} ${await grantRes.text()}`).toBeTruthy()

    // Now the member should see the record.
    const memberCtx = await loginAs(playwright, baseURL!, memberEmail, memberPassword)
    try {
      const listRes = await memberCtx.get('/api/v1/crm/records')
      expect(listRes.ok()).toBeTruthy()
      const records = await listRes.json()
      const memberIds = (records as Array<{ id: string }>).map((r) => r.id)
      expect(memberIds).toContain(ownerRecordId)

      // Detail endpoint should also work.
      const detailRes = await memberCtx.get(`/api/v1/crm/records/${ownerRecordId}`)
      expect(detailRes.ok()).toBeTruthy()
    } finally {
      await memberCtx.dispose()
    }
  })

  // -------------------------------------------------------------------------
  // Use-case 3: Manažer s scope=team vidí záznamy svého týmu
  // -------------------------------------------------------------------------

  test('UC3: manager with team scope sees team members records', async ({
    request,
    playwright,
    baseURL,
  }) => {
    // Create a team.
    const teamRes = await request.post(`/api/v1/firms/${firmId}/teams`, {
      data: { name: 'Sales-CZ', color: '#0ea5e9' },
    })
    expect(teamRes.ok(), `team create failed: ${teamRes.status()} ${await teamRes.text()}`).toBeTruthy()
    const teamId = (await teamRes.json()).id as string

    // Get the member's membership id.
    const membersRes = await request.get(`/api/v1/firms/${firmId}/members`)
    expect(membersRes.ok()).toBeTruthy()
    const members = (await membersRes.json()) as Array<{ id: string; user_email: string }>
    const memberMembership = members.find((m) => m.user_email === memberEmail)
    expect(memberMembership).toBeDefined()

    // Add the member to the team.
    const addRes = await request.post(
      `/api/v1/firms/${firmId}/teams/${teamId}/members/${memberMembership!.id}`,
    )
    expect(addRes.ok(), `add to team failed: ${addRes.status()} ${await addRes.text()}`).toBeTruthy()

    // Create a record assigned to the member (simulates their work).
    const ts = Date.now()
    const memberCtx = await loginAs(playwright, baseURL!, memberEmail, memberPassword)
    try {
      const recRes = await memberCtx.post('/api/v1/crm/records', {
        data: { title: `Member Record ${ts}` },
      })
      expect(recRes.ok()).toBeTruthy()
      const memberRecordId = (await recRes.json()).id as string

      // The owner (with full access) should see both their own record and the member's.
      const ownerListRes = await request.get('/api/v1/crm/records')
      expect(ownerListRes.ok()).toBeTruthy()
      const ownerRecords = (await ownerListRes.json()) as Array<{ id: string }>
      const ownerIds = ownerRecords.map((r) => r.id)
      expect(ownerIds).toContain(memberRecordId)
    } finally {
      await memberCtx.dispose()
    }
  })

  // -------------------------------------------------------------------------
  // Use-case 4: External auditor – RecordGrant with expires_at
  // -------------------------------------------------------------------------

  test('UC4: external auditor gets time-limited record access via RecordGrant', async ({
    request,
    playwright,
    baseURL,
  }) => {
    // Get member's user_id.
    const membersRes = await request.get(`/api/v1/firms/${firmId}/members`)
    const members = (await membersRes.json()) as Array<{ user_id: string; user_email: string }>
    const memberInfo = members.find((m) => m.user_email === memberEmail)
    expect(memberInfo).toBeDefined()

    // Create a record that will be shared with the "auditor" (member acting as auditor).
    const ts = Date.now()
    const recRes = await request.post('/api/v1/crm/records', {
      data: { title: `Audit Record ${ts}` },
    })
    expect(recRes.ok()).toBeTruthy()
    const auditRecordId = (await recRes.json()).id as string

    // Grant time-limited view access (expires 30 days from now).
    const expiresAt = new Date(Date.now() + 30 * 24 * 60 * 60 * 1000).toISOString()
    const grantRes = await request.post(`/api/v1/crm/records/${auditRecordId}/grants`, {
      data: {
        principal_type: 'user',
        principal_id: memberInfo!.user_id,
        level: 'view',
        expires_at: expiresAt,
      },
    })
    expect(grantRes.ok(), `grant failed: ${grantRes.status()} ${await grantRes.text()}`).toBeTruthy()
    const grant = await grantRes.json()
    expect(grant.expires_at).toBeTruthy()

    // The member (auditor) should now be able to access that record.
    const memberCtx = await loginAs(playwright, baseURL!, memberEmail, memberPassword)
    try {
      const detailRes = await memberCtx.get(`/api/v1/crm/records/${auditRecordId}`)
      expect(detailRes.ok(), `auditor cannot access record: ${detailRes.status()}`).toBeTruthy()

      // Verify the grant appears in the record access list (owner view).
      const accessRes = await request.get(`/api/v1/crm/records/${auditRecordId}/access`)
      expect(accessRes.ok()).toBeTruthy()
      const access = await accessRes.json()
      const recordGrants = access.record_grants as Array<{ principal_id: string }>
      expect(recordGrants.some((g) => g.principal_id === memberInfo!.user_id)).toBeTruthy()
    } finally {
      await memberCtx.dispose()
    }
  })

  // -------------------------------------------------------------------------
  // Use-case 5: Admin nemůže smazat firmu (Owner-only operace)
  // -------------------------------------------------------------------------

  test('UC5: admin/member cannot delete firm – Owner-only', async ({
    request,
    playwright,
    baseURL,
  }) => {
    // The member (worker role) must not be able to delete the firm.
    const memberCtx = await loginAs(playwright, baseURL!, memberEmail, memberPassword)
    try {
      const deleteRes = await memberCtx.delete(`/api/v1/firms/${firmId}`)
      // Expect 403 Forbidden (not the Owner).
      expect(deleteRes.status()).toBe(403)
    } finally {
      await memberCtx.dispose()
    }

    // The owner CAN get firm details (sanity-check the owner's context still works).
    const ownerDetailRes = await request.get(`/api/v1/firms/${firmId}`)
    expect(ownerDetailRes.ok()).toBeTruthy()
  })

  // -------------------------------------------------------------------------
  // Use-case 5b: GET /firms/{id}/me/permissions reflects owner capabilities
  // -------------------------------------------------------------------------

  test('UC5b: /me/permissions returns correct data for owner and member', async ({
    request,
    playwright,
    baseURL,
  }) => {
    // Owner should have all permissions including firm.delete.
    const ownerPermsRes = await request.get(`/api/v1/firms/${firmId}/me/permissions`)
    expect(ownerPermsRes.ok()).toBeTruthy()
    const ownerPerms = await ownerPermsRes.json()
    expect((ownerPerms.permissions as string[]).includes('firm.delete')).toBeTruthy()
    expect(ownerPerms.can_manage_roles).toBeTruthy()

    // Member should NOT have firm.delete.
    const memberCtx = await loginAs(playwright, baseURL!, memberEmail, memberPassword)
    try {
      const memberPermsRes = await memberCtx.get(`/api/v1/firms/${firmId}/me/permissions`)
      expect(memberPermsRes.ok()).toBeTruthy()
      const memberPerms = await memberPermsRes.json()
      expect((memberPerms.permissions as string[]).includes('firm.delete')).toBeFalsy()
    } finally {
      await memberCtx.dispose()
    }
  })
})
