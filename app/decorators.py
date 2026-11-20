"""Guards for protecting routes."""
from functools import wraps

from flask import abort, flash, redirect, request, session, url_for


def login_required(view):
    """Only allow logged-in users; send everyone else to the login page."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Please log in to continue.", "warning")
            return redirect(url_for("auth.login", next=request.url))
        return view(*args, **kwargs)

    return wrapped


def admin_required(view):
    """Only allow users with the admin role."""
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if session.get("role") != "admin":
            abort(403)
        return view(*args, **kwargs)

    return wrapped
