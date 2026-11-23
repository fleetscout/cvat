# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

from rest_framework import status

from cvat.apps.engine.models import (
    Issue,
    Job,
    Label,
    LabeledShape,
    StageChoice,
    StateChoice,
    StatusChoice,
)
from cvat.apps.engine.tests.test_rest_api import create_db_users, create_dummy_db_tasks
from cvat.apps.engine.tests.utils import ApiTestBase, ForceLogin
from cvat.apps.fs_workflow.models import JobPeople


class JobPeopleAPITestCase(ApiTestBase):
    @classmethod
    def setUpTestData(cls):
        create_db_users(cls)

    def setUp(self):
        super().setUp()

        self.task = create_dummy_db_tasks(self)[0]
        self.job = Job.objects.get(segment__task_id=self.task.id)
        self.job.assignee = self.annotator
        self.job.save()

        self.reviewer = self.user5

    def _send(self, user, data=None, job_id=None):
        with ForceLogin(user, self.client):
            return self.client.post(
                f"/api/jobs/{job_id or self.job.id}/send_to_review", data=data or {}, format="json"
            )

    def _patch(self, user, data):
        with ForceLogin(user, self.client):
            return self.client.patch(f"/api/jobs/{self.job.id}/people", data=data, format="json")

    def _list(self, user, ids):
        with ForceLogin(user, self.client):
            return self.client.get("/api/jobs/people", {"ids": ",".join(map(str, ids))})

    def test_annotator_can_send_their_job_to_review(self):
        response = self._send(self.annotator, {"reviewer": self.reviewer.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.job.refresh_from_db()
        self.assertEqual(self.job.stage, StageChoice.VALIDATION)
        self.assertEqual(self.job.state, StateChoice.NEW)
        self.assertEqual(self.job.status, StatusChoice.VALIDATION)
        self.assertEqual(self.job.assignee_id, self.reviewer.id)

        people = JobPeople.objects.get(job=self.job)
        self.assertEqual(people.annotator_id, self.annotator.id)
        self.assertEqual(people.reviewer_id, self.reviewer.id)

    def test_send_to_review_uses_the_saved_reviewer(self):
        JobPeople.objects.create(job=self.job, reviewer=self.reviewer)

        response = self._send(self.annotator)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.job.refresh_from_db()
        self.assertEqual(self.job.assignee_id, self.reviewer.id)

    def test_send_to_review_without_a_reviewer_leaves_it_unassigned(self):
        response = self._send(self.annotator)

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.job.refresh_from_db()
        self.assertEqual(self.job.stage, StageChoice.VALIDATION)
        self.assertIsNone(self.job.assignee_id)

    def test_someone_else_cannot_send_the_job_to_review(self):
        response = self._send(self.somebody)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.job.refresh_from_db()
        self.assertEqual(self.job.stage, StageChoice.ANNOTATION)

    def test_only_annotation_jobs_can_be_sent_to_review(self):
        self.job.stage = StageChoice.VALIDATION
        self.job.save()

        response = self._send(self.admin)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejects_an_unknown_reviewer(self):
        response = self._send(self.annotator, {"reviewer": 99999})

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.job.refresh_from_db()
        self.assertEqual(self.job.stage, StageChoice.ANNOTATION)

    def test_setting_the_reviewer_while_annotating_keeps_the_job_with_the_annotator(self):
        response = self._patch(self.owner, {"reviewer": self.reviewer.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(response.data["annotator"]["id"], self.annotator.id)
        self.assertEqual(response.data["reviewer"]["id"], self.reviewer.id)
        self.job.refresh_from_db()
        self.assertEqual(self.job.assignee_id, self.annotator.id)

    def test_changing_the_annotator_while_annotating_hands_the_job_over(self):
        response = self._patch(self.owner, {"annotator": self.assignee.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.job.refresh_from_db()
        self.assertEqual(self.job.assignee_id, self.assignee.id)

    def test_changing_the_reviewer_during_review_hands_the_job_over(self):
        self._send(self.annotator, {"reviewer": self.reviewer.id})

        response = self._patch(self.owner, {"reviewer": self.assignee.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.job.refresh_from_db()
        self.assertEqual(self.job.assignee_id, self.assignee.id)
        self.assertEqual(response.data["annotator"]["id"], self.annotator.id)

    def test_annotator_cannot_change_people(self):
        response = self._patch(self.annotator, {"reviewer": self.reviewer.id})

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_list_shows_both_people(self):
        self._send(self.annotator, {"reviewer": self.reviewer.id})

        response = self._list(self.owner, [self.job.id])

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertEqual(len(response.data), 1)
        self.assertEqual(response.data[0]["job_id"], self.job.id)
        self.assertEqual(response.data[0]["annotator"]["username"], self.annotator.username)
        self.assertEqual(response.data[0]["reviewer"]["username"], self.reviewer.username)

    def test_list_without_saved_people_shows_the_assignee_as_annotator(self):
        response = self._list(self.owner, [self.job.id])

        self.assertEqual(response.data[0]["annotator"]["id"], self.annotator.id)
        self.assertIsNone(response.data[0]["reviewer"])

    def test_list_leaves_out_jobs_the_user_cannot_see(self):
        response = self._list(self.somebody, [self.job.id])

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data, [])

    def test_list_rejects_bad_ids(self):
        response = self._list(self.owner, ["abc"])

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rejected_frames_go_back_to_the_annotator(self):
        self._send(self.annotator, {"reviewer": self.reviewer.id})
        label = Label.objects.create(task=self.task, name="dent")
        LabeledShape.objects.create(
            job=self.job, label=label, frame=3, group=0, type="rectangle", points=[1, 2, 3, 4]
        )
        Issue.objects.create(
            job=self.job, frame=3, position=[1, 2, 3, 4], owner=self.owner, resolved=False
        )

        with ForceLogin(self.owner, self.client):
            response = self.client.post(
                f"/api/jobs/{self.job.id}/return_flagged_frames", data={}, format="json"
            )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED, response.data)
        new_job = Job.objects.get(pk=response.data["id"])
        self.assertEqual(new_job.assignee_id, self.annotator.id)
        people = JobPeople.objects.get(job=new_job)
        self.assertEqual(people.annotator_id, self.annotator.id)
        self.assertEqual(people.reviewer_id, self.reviewer.id)

    def test_the_accepted_job_keeps_its_reviewer_after_sending_frames_back(self):
        self.job.stage = StageChoice.VALIDATION
        self.job.assignee = self.reviewer
        self.job.save()
        label = Label.objects.create(task=self.task, name="dent")
        LabeledShape.objects.create(
            job=self.job, label=label, frame=3, group=0, type="rectangle", points=[1, 2, 3, 4]
        )
        Issue.objects.create(
            job=self.job, frame=3, position=[1, 2, 3, 4], owner=self.owner, resolved=False
        )

        with ForceLogin(self.owner, self.client):
            self.client.post(
                f"/api/jobs/{self.job.id}/return_flagged_frames", data={}, format="json"
            )

        response = self._list(self.owner, [self.job.id])
        self.assertEqual(response.data[0]["reviewer"]["id"], self.reviewer.id)

    def test_saving_people_with_no_changes_keeps_the_reviewer_on_record(self):
        self.job.stage = StageChoice.VALIDATION
        self.job.assignee = self.reviewer
        self.job.save()

        self.assertEqual(self._patch(self.owner, {}).status_code, status.HTTP_200_OK)
        self.job.stage = StageChoice.ACCEPTANCE
        self.job.save()

        response = self._list(self.owner, [self.job.id])
        self.assertEqual(response.data[0]["reviewer"]["id"], self.reviewer.id)

    def test_a_lead_sending_an_unassigned_job_is_not_recorded_as_its_annotator(self):
        self.job.assignee = None
        self.job.save()

        response = self._send(self.owner, {"reviewer": self.reviewer.id})

        self.assertEqual(response.status_code, status.HTTP_200_OK, response.data)
        self.assertIsNone(JobPeople.objects.get(job=self.job).annotator_id)
