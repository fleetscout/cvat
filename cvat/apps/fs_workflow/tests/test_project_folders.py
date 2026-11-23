# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

import json

from django.contrib.auth.models import Group
from rest_framework import status

from cvat.apps.engine.models import Project
from cvat.apps.engine.tests.test_rest_api import create_db_users
from cvat.apps.engine.tests.utils import ApiTestBase, ForceLogin
from cvat.apps.fs_workflow.models import ProjectFolder, ProjectFolderItem
from cvat.apps.organizations.models import Membership, Organization


class ProjectFolderOrganizationTestCase(ApiTestBase):
    @classmethod
    def setUpTestData(cls):
        create_db_users(cls)

    def setUp(self):
        super().setUp()
        self.org = Organization.objects.create(slug="fleet", name="Fleet", owner=self.owner)
        Membership.objects.create(
            user=self.owner, organization=self.org, role="owner", is_active=True
        )
        Membership.objects.create(
            user=self.assignee, organization=self.org, role="maintainer", is_active=True
        )
        Membership.objects.create(
            user=self.annotator, organization=self.org, role="worker", is_active=True
        )
        for user in (self.owner, self.assignee):
            user.groups.add(Group.objects.get_or_create(name="user")[0])
        self.current = Project.objects.create(
            name="Current", owner=self.owner, organization=self.org
        )
        self.old = Project.objects.create(name="Old", owner=self.owner, organization=self.org)
        self.outside = Project.objects.create(name="Elsewhere", owner=self.owner)

    def _call(self, user, method, path, data=None):
        with ForceLogin(user, self.client):
            sep = "&" if "?" in path else "?"
            return getattr(self.client, method)(f"{path}{sep}org=fleet", data=data, format="json")

    def _make_folder(self, user=None, name="Old projects"):
        return self._call(user or self.assignee, "post", "/api/project_folders", {"name": name})

    def _project_names(self, user, rule):
        response = self._call(user, "get", f"/api/projects?filter={json.dumps(rule)}")
        return sorted(p["name"] for p in response.data["results"])

    def test_maintainer_files_projects_and_the_main_list_hides_them(self):
        folder = self._make_folder().data
        response = self._call(
            self.assignee,
            "post",
            f"/api/project_folders/{folder['id']}/add_projects",
            {"projects": [self.old.id]},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["project_count"], 1)

        self.assertEqual(self._project_names(self.owner, {"!": {"var": "folder"}}), ["Current"])
        self.assertEqual(
            self._project_names(self.owner, {"==": [{"var": "folder"}, folder["id"]]}), ["Old"]
        )

    def test_removing_puts_the_project_back(self):
        folder = self._make_folder().data
        self._call(
            self.assignee,
            "post",
            f"/api/project_folders/{folder['id']}/add_projects",
            {"projects": [self.old.id]},
        )
        response = self._call(
            self.assignee,
            "post",
            f"/api/project_folders/{folder['id']}/remove_projects",
            {"projects": [self.old.id]},
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertFalse(ProjectFolderItem.objects.exists())

    def test_moving_between_folders(self):
        first, second = self._make_folder(name="A").data, self._make_folder(name="B").data
        for folder in (first, second):
            self._call(
                self.assignee,
                "post",
                f"/api/project_folders/{folder['id']}/add_projects",
                {"projects": [self.old.id]},
            )
        self.assertEqual(ProjectFolderItem.objects.get(project=self.old).folder_id, second["id"])

    def test_worker_sees_folders_but_cannot_change_them(self):
        folder = self._make_folder().data
        listed = self._call(self.annotator, "get", "/api/project_folders")
        self.assertEqual([f["name"] for f in listed.data], ["Old projects"])
        self.assertEqual(self._make_folder(self.annotator).status_code, status.HTTP_403_FORBIDDEN)
        for path, data in (
            (f"/api/project_folders/{folder['id']}/add_projects", {"projects": [self.old.id]}),
            (f"/api/project_folders/{folder['id']}/remove_projects", {"projects": [self.old.id]}),
        ):
            self.assertEqual(
                self._call(self.annotator, "post", path, data).status_code,
                status.HTTP_403_FORBIDDEN,
            )
        self.assertEqual(
            self._call(
                self.annotator, "patch", f"/api/project_folders/{folder['id']}", {"name": "x"}
            ).status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_cannot_file_a_project_from_outside_the_organization(self):
        folder = self._make_folder().data
        response = self._call(
            self.owner,
            "post",
            f"/api/project_folders/{folder['id']}/add_projects",
            {"projects": [self.outside.id]},
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rename_and_delete(self):
        folder = self._make_folder().data
        self._call(
            self.assignee,
            "post",
            f"/api/project_folders/{folder['id']}/add_projects",
            {"projects": [self.old.id]},
        )
        renamed = self._call(
            self.assignee, "patch", f"/api/project_folders/{folder['id']}", {"name": "Archive"}
        )
        self.assertEqual(renamed.data["name"], "Archive")
        deleted = self._call(self.assignee, "delete", f"/api/project_folders/{folder['id']}")
        self.assertEqual(deleted.status_code, status.HTTP_204_NO_CONTENT)
        self.assertTrue(Project.objects.filter(pk=self.old.pk).exists())
        self.assertFalse(ProjectFolderItem.objects.exists())

    def test_blank_name_is_refused(self):
        self.assertEqual(self._make_folder(name="  ").status_code, status.HTTP_400_BAD_REQUEST)

    def test_folders_of_other_organizations_are_hidden(self):
        other = Organization.objects.create(slug="other", name="Other", owner=self.somebody)
        ProjectFolder.objects.create(organization=other, owner=self.somebody, name="Theirs")
        self._make_folder()
        listed = self._call(self.annotator, "get", "/api/project_folders")
        self.assertEqual([f["name"] for f in listed.data], ["Old projects"])
