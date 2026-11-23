# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from enum import StrEnum

from django.conf import settings

from cvat.apps.iam.permissions import OpenPolicyAgentPermission

from .models import ProjectFolder


class ProjectFolderPermission(OpenPolicyAgentPermission):
    obj: ProjectFolder | None

    class Scopes(StrEnum):
        CREATE = "create"
        LIST = "list"
        VIEW = "view"
        UPDATE = "update"
        DELETE = "delete"
        UPDATE_PROJECTS = "update:projects"

    @classmethod
    def create(cls, request, view, obj, iam_context):
        return [
            cls.create_base_perm(request, view, scope, iam_context, obj)
            for scope in cls.get_scopes(request, view, obj)
        ]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.url = settings.IAM_OPA_DATA_URL + "/project_folders/allow"

    @classmethod
    def _get_scopes(cls, request, view, obj):
        Scopes = cls.Scopes
        return [
            {
                ("list", "GET"): Scopes.LIST,
                ("create", "POST"): Scopes.CREATE,
                ("retrieve", "GET"): Scopes.VIEW,
                ("partial_update", "PATCH"): Scopes.UPDATE,
                ("destroy", "DELETE"): Scopes.DELETE,
                ("add_projects", "POST"): Scopes.UPDATE_PROJECTS,
                ("remove_projects", "POST"): Scopes.UPDATE_PROJECTS,
            }[(view.action, request.method)]
        ]

    def get_resource(self):
        if self.obj:
            return {
                "id": self.obj.id,
                "owner": self.make_id_dict(self.obj.owner_id),
                "organization": self.make_id_dict(self.obj.organization_id),
            }
        if self.scope == self.Scopes.CREATE:
            return {
                "id": None,
                "owner": {"id": self.user_id},
                "organization": self.make_id_dict(self.org_id),
            }
        return None
