# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from django.conf import settings
from django.db import models


class JobPeople(models.Model):
    """
    Who annotates and who reviews a job.

    A job has one assignee, which changes hands as the job moves between stages.
    This keeps both people, so the board can show them and a rejected job can
    go back to its annotator.

    It lives in its own app so its migrations stay out of the engine app's history.
    """

    job = models.OneToOneField(
        "engine.Job", on_delete=models.CASCADE, primary_key=True, related_name="people"
    )
    annotator = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        default_permissions = ()


class ProjectFolder(models.Model):
    """A folder on the projects page, shared by everyone in the organisation, to tidy away projects."""

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="+",
    )
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    name = models.CharField(max_length=64)
    created_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        default_permissions = ()
        ordering = ["name", "id"]


class ProjectFolderItem(models.Model):
    """The folder a project is in. Projects with no row are on the main projects page."""

    project = models.OneToOneField(
        "engine.Project", on_delete=models.CASCADE, primary_key=True, related_name="folder"
    )
    folder = models.ForeignKey(ProjectFolder, on_delete=models.CASCADE, related_name="items")

    class Meta:
        default_permissions = ()
