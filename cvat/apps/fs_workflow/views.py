# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from django.db import transaction
from django.db.models import Count
from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from cvat.apps.engine.models import Project
from cvat.apps.engine.permissions import ProjectPermission

from .models import ProjectFolder, ProjectFolderItem
from .permissions import ProjectFolderPermission
from .serializers import ProjectFolderProjectsSerializer, ProjectFolderSerializer


@extend_schema(tags=["project_folders"])
@extend_schema_view(
    list=extend_schema(summary="List the folders on the projects page"),
    create=extend_schema(summary="Create a folder"),
    retrieve=extend_schema(summary="Get a folder"),
    partial_update=extend_schema(summary="Rename a folder"),
    destroy=extend_schema(
        summary="Delete a folder. Its projects go back to the main projects page"
    ),
)
class ProjectFolderViewSet(
    viewsets.GenericViewSet,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    mixins.DestroyModelMixin,
):
    queryset = ProjectFolder.objects.all()
    serializer_class = ProjectFolderSerializer
    iam_permission_class = ProjectFolderPermission
    iam_supports_organization_params = True
    http_method_names = ("get", "post", "patch", "delete", "head", "options")
    pagination_class = None
    search_fields = ("name",)
    simple_filters = ("name",)
    filter_fields = ("name", "id")
    ordering_fields = ("name", "id")
    ordering = "name"

    def get_queryset(self):
        queryset = super().get_queryset().annotate(project_count=Count("items"))
        if self.action == "list":
            queryset = ProjectFolderPermission.create_scope_list(self.request).filter(queryset)
        return queryset

    def perform_create(self, serializer):
        serializer.save(
            owner=self.request.user, organization=self.request.iam_context["organization"]
        )

    def _visible_projects(self, request, folder: ProjectFolder, ids: list[int]) -> list[Project]:
        perm = ProjectPermission.create_scope_list(request)
        projects = list(perm.filter(Project.objects.filter(id__in=ids)))
        missing = set(ids) - {p.id for p in projects}
        if missing:
            raise ValidationError(f"Projects not found: {', '.join(map(str, sorted(missing)))}")
        elsewhere = [p.id for p in projects if p.organization_id != folder.organization_id]
        if elsewhere:
            raise ValidationError(
                f"Projects from another organization: {', '.join(map(str, sorted(elsewhere)))}"
            )
        return projects

    @extend_schema(
        summary="Put projects in this folder",
        description="Projects already in another folder move to this one.",
        request=ProjectFolderProjectsSerializer,
        responses={"200": ProjectFolderSerializer},
    )
    @action(detail=True, methods=["POST"], url_path="add_projects")
    def add_projects(self, request, pk: int):
        folder = self.get_object()
        serializer = ProjectFolderProjectsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        projects = self._visible_projects(request, folder, serializer.validated_data["projects"])
        with transaction.atomic():
            for project in projects:
                ProjectFolderItem.objects.update_or_create(
                    project=project, defaults={"folder": folder}
                )
        return Response(ProjectFolderSerializer(self.get_queryset().get(pk=folder.pk)).data)

    @extend_schema(
        summary="Take projects out of this folder",
        description="They go back to the main projects page.",
        request=ProjectFolderProjectsSerializer,
        responses={
            "200": ProjectFolderSerializer,
            "400": OpenApiResponse(description="Bad project IDs"),
        },
    )
    @action(detail=True, methods=["POST"], url_path="remove_projects")
    def remove_projects(self, request, pk: int):
        folder = self.get_object()
        serializer = ProjectFolderProjectsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ProjectFolderItem.objects.filter(
            folder=folder, project_id__in=serializer.validated_data["projects"]
        ).delete()
        return Response(
            ProjectFolderSerializer(self.get_queryset().get(pk=folder.pk)).data,
            status=status.HTTP_200_OK,
        )
