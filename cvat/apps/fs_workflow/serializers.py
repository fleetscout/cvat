# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from rest_framework import serializers

from .models import ProjectFolder


class ProjectFolderSerializer(serializers.ModelSerializer):
    project_count = serializers.IntegerField(read_only=True)
    organization = serializers.IntegerField(
        source="organization_id", read_only=True, allow_null=True
    )
    owner = serializers.IntegerField(source="owner_id", read_only=True, allow_null=True)

    class Meta:
        model = ProjectFolder
        fields = ("id", "name", "organization", "owner", "created_date", "project_count")
        read_only_fields = ("id", "organization", "owner", "created_date", "project_count")

    def validate_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("A folder needs a name")
        return value


class ProjectFolderProjectsSerializer(serializers.Serializer):
    projects = serializers.ListField(child=serializers.IntegerField(), min_length=1, max_length=500)
