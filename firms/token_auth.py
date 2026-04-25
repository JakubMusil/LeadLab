"""
firms.token_auth
================
Django Ninja authentication backend that accepts API tokens transmitted via
the ``Authorization: Bearer <token>`` HTTP header.

The auth object resolves both ``request.user`` and ``request.firm`` /
``request.membership`` so that existing ``require_membership`` guards work
without modification when a token is used.
"""

from ninja.security import HttpBearer

from firms.models import APIToken, Membership


class BearerTokenAuth(HttpBearer):
    """
    Accept requests that carry a valid ``Authorization: Bearer <token>``
    header.  The token is validated against the ``APIToken`` table; on
    success the request gains the identity of the token owner within the
    token's firm.
    """

    def authenticate(self, request, token: str):
        api_token = APIToken.authenticate(token)
        if api_token is None:
            return None

        # Attach the user so that existing auth helpers see an authenticated
        # request (mirrors what Django's session middleware does).
        request.user = api_token.user
        request._token_firm = api_token.firm

        # Attach firm + membership so ``require_membership`` works.
        request.firm = api_token.firm
        request.membership = (
            Membership.objects.select_related("user", "firm")
            .filter(user=api_token.user, firm=api_token.firm)
            .first()
        )

        return api_token.user
