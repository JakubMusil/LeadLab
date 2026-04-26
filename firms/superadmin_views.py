import json
from django.contrib.admin.views.decorators import staff_member_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth import login
from firms.models import Firm, Membership
from users.models import User

@staff_member_required
def superadmin_firms(request):
    firms = []
    for firm in Firm.objects.all().prefetch_related('memberships'):
        firms.append({
            'id': str(firm.id),
            'name': firm.name,
            'slug': firm.slug,
            'subscription_tier': firm.subscription_tier,
            'subscription_active': firm.subscription_active,
            'is_active': firm.is_active,
            'member_count': firm.memberships.count(),
        })
    return JsonResponse({'firms': firms})

@csrf_exempt
@staff_member_required
@require_http_methods(['POST'])
def superadmin_adjust_subscription(request, firm_id):
    try:
        firm = Firm.objects.get(id=firm_id)
    except Firm.DoesNotExist:
        return JsonResponse({'detail': 'Firm not found.'}, status=404)
    data = json.loads(request.body or '{}')
    if 'subscription_tier' in data:
        firm.subscription_tier = data['subscription_tier']
    if 'subscription_active' in data:
        firm.subscription_active = bool(data['subscription_active'])
    firm.save()
    return JsonResponse({'id': str(firm.id), 'subscription_tier': firm.subscription_tier, 'subscription_active': firm.subscription_active})

@csrf_exempt
@staff_member_required
@require_http_methods(['POST'])
def superadmin_impersonate(request, user_id):
    try:
        user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'detail': 'User not found.'}, status=404)
    request.session['impersonator_id'] = str(request.user.id)
    login(request, user, backend='django.contrib.auth.backends.ModelBackend')
    return JsonResponse({'detail': f'Now impersonating {user.email}'})

@staff_member_required
def superadmin_stop_impersonation(request):
    impersonator_id = request.session.pop('impersonator_id', None)
    if impersonator_id:
        try:
            original = User.objects.get(id=impersonator_id)
            login(request, original, backend='django.contrib.auth.backends.ModelBackend')
            return JsonResponse({'detail': 'Impersonation ended.'})
        except User.DoesNotExist:
            pass
    return JsonResponse({'detail': 'Not impersonating.'})
