"""OpenAPI schema customizations for the public API documentation."""

from drf_spectacular.openapi import AutoSchema


class CategorizedAutoSchema(AutoSchema):
    """Give Swagger operations stable, feature-oriented category tags."""

    MODULE_TAGS = {
        "Apps.abilities": "Abilities",
        "Apps.feedback": "Feedback",
        "Apps.learning": "Learning",
        "Apps.legal": "Legal",
        "Apps.notifications": "Notifications",
        "Apps.profiles": "Profile & Account",
        "Apps.progress": "Progress",
        "Apps.resources": "Resources",
        "Apps.subscriptions": "Subscriptions",
        "Apps.support": "Support",
    }

    def get_tags(self):
        path = self.path.removeprefix("/")
        module = self.view.__class__.__module__

        # Some apps expose more than one user-facing feature area.
        if path.startswith("api/v1/auth/"):
            return ["Authentication"]
        if path.startswith("api/v1/user/"):
            return ["Profile & Account"]
        if module == "Apps.journey.views":
            if path.startswith("api/v1/onboarding/"):
                return ["Onboarding"]
            return ["Journey"]

        for module_prefix, tag in self.MODULE_TAGS.items():
            if module.startswith(module_prefix):
                return [tag]

