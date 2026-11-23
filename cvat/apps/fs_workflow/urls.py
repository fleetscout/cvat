# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from rest_framework import routers

from .views import ProjectFolderViewSet

router = routers.DefaultRouter(trailing_slash=False)
router.register("project_folders", ProjectFolderViewSet)

urlpatterns = router.urls
