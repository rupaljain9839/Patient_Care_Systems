"""Route-protection decorator for Flask views — mirrors what st.session_state['user']
checks did in the Streamlit app, but as a proper Flask decorator."""
from functools import wraps

from flask import session, redirect, url_for


class login_required:
    """Class-based decorator to protect Flask routes.

    Usage:
        @some_bp.route("/somewhere")
        @login_required(role="patient")
        def somewhere():
            ...

    Implements descriptor protocol so it works on functions and methods.
    """

    def __init__(self, role=None):
        self.role = role

    def __call__(self, f):
        # Support decorating callables: return a wrapped function
        @wraps(f)
        def wrapped(*args, **kwargs):
            user = session.get("user")
            if not user:
                return redirect(url_for("auth.login"))
            if self.role and user.get("role") != self.role:
                return redirect(url_for("auth.login"))
            return f(*args, **kwargs)

        # preserve an attribute to allow introspection if needed
        wrapped._original = f
        return wrapped

    def __get__(self, obj, objtype=None):
        # Support using the decorator on instance methods
        # When accessed as a descriptor, return a bound method where the
        # underlying function is wrapped with the same checks.
        def bind(f):
            @wraps(f)
            def wrapped(*args, **kwargs):
                user = session.get("user")
                if not user:
                    return redirect(url_for("auth.login"))
                if self.role and user.get("role") != self.role:
                    return redirect(url_for("auth.login"))
                return f(*args, **kwargs)

            wrapped._original = f
            return wrapped

        # If obj is None, accessed on class, just return self to be used as decorator
        if obj is None:
            return self

        # For instance access, we need to return a function bound to the instance.
        # The descriptor is used like: @login_required(...) def method(self,...)
        # but Python already applies descriptor to functions; here we return a
        # callable that will wrap the original function when called with the instance.
        return lambda f: bind(f).__get__(obj, objtype)


# keep compatibility: allow usage as @login_required(...) returning decorator
# by leaving the class name as the callable constructor