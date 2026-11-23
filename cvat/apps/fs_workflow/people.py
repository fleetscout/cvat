# Copyright (C) CVAT.ai Corporation
#
# SPDX-License-Identifier: MIT

"""
The annotator and reviewer of a job.

The job's assignee is whoever holds it now: the annotator during annotation
and the reviewer during validation. The other person is kept in JobPeople.
"""

from collections.abc import Iterable
from dataclasses import dataclass

from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework.exceptions import ValidationError

from cvat.apps.engine import models as engine_models

from .models import JobPeople

User = get_user_model()

UNSET = object()


@dataclass(frozen=True)
class People:
    annotator: User | None
    reviewer: User | None


def _effective(db_job: engine_models.Job, db_people: JobPeople | None) -> People:
    annotator = db_people.annotator if db_people else None
    reviewer = db_people.reviewer if db_people else None

    # The assignee is the source of truth for whoever holds the job now
    if db_job.stage == engine_models.StageChoice.ANNOTATION:
        annotator = db_job.assignee
    elif db_job.stage == engine_models.StageChoice.VALIDATION:
        reviewer = db_job.assignee

    return People(annotator=annotator, reviewer=reviewer)


def get_people(db_job: engine_models.Job) -> People:
    db_people = JobPeople.objects.select_related("annotator", "reviewer").filter(job=db_job).first()
    return _effective(db_job, db_people)


def get_people_for_jobs(db_jobs: Iterable[engine_models.Job]) -> dict[int, People]:
    db_jobs = list(db_jobs)
    stored = {
        p.job_id: p
        for p in JobPeople.objects.select_related("annotator", "reviewer").filter(
            job_id__in=[j.id for j in db_jobs]
        )
    }
    return {j.id: _effective(j, stored.get(j.id)) for j in db_jobs}


def _check_users(db_job: engine_models.Job, user_ids: Iterable[int]) -> None:
    user_ids = set(user_ids)
    if not user_ids:
        return

    found = set(User.objects.filter(id__in=user_ids, is_active=True).values_list("id", flat=True))
    missing = user_ids - found
    if missing:
        raise ValidationError(
            "These users do not exist or are inactive: {}".format(", ".join(map(str, missing)))
        )

    if db_job.organization_id is not None:
        from cvat.apps.organizations.models import Membership

        members = set(
            Membership.objects.filter(
                organization_id=db_job.organization_id, user_id__in=user_ids, is_active=True
            ).values_list("user_id", flat=True)
        )
        outsiders = user_ids - members
        if outsiders:
            raise ValidationError(
                "These users are not members of the organization: {}".format(
                    ", ".join(map(str, outsiders))
                )
            )


@transaction.atomic
def set_people(
    job_id: int,
    *,
    annotator_id: int | None | object = UNSET,
    reviewer_id: int | None | object = UNSET,
) -> engine_models.Job:
    """
    Changes the annotator and/or the reviewer of a job.
    If the job is with the person being changed, it is handed to the new person.
    """

    db_job = engine_models.Job.objects.select_for_update().get(id=job_id)
    _check_users(db_job, [i for i in (annotator_id, reviewer_id) if isinstance(i, int)])

    db_people, _ = JobPeople.objects.get_or_create(job=db_job)
    current = _effective(db_job, db_people)
    db_people.annotator = current.annotator
    db_people.reviewer = current.reviewer

    holder_id = UNSET
    if annotator_id is not UNSET:
        db_people.annotator_id = annotator_id
        if db_job.stage == engine_models.StageChoice.ANNOTATION:
            holder_id = annotator_id
    if reviewer_id is not UNSET:
        db_people.reviewer_id = reviewer_id
        if db_job.stage == engine_models.StageChoice.VALIDATION:
            holder_id = reviewer_id

    db_people.save()

    if holder_id is not UNSET and holder_id != db_job.assignee_id:
        db_job.update_assignee(holder_id)
        db_job.save(update_fields=["assignee", "assignee_updated_date", "updated_date"])

    return db_job


@transaction.atomic
def send_to_review(job_id: int, *, reviewer_id: int | None | object = UNSET) -> engine_models.Job:
    """
    Moves a job from annotation to review and hands it to the reviewer.
    The person who held the job is remembered as its annotator.
    """

    db_job = engine_models.Job.objects.select_for_update().get(id=job_id)
    if db_job.stage != engine_models.StageChoice.ANNOTATION:
        raise ValidationError("Only jobs in the annotation stage can be sent to review")

    if isinstance(reviewer_id, int):
        _check_users(db_job, [reviewer_id])

    db_people, _ = JobPeople.objects.get_or_create(job=db_job)
    # Whoever holds the job annotated it. A lead sending an unassigned job leaves the annotator as it was.
    if db_job.assignee_id:
        db_people.annotator_id = db_job.assignee_id
    if reviewer_id is not UNSET:
        db_people.reviewer_id = reviewer_id
    db_people.save()

    db_job.stage = engine_models.StageChoice.VALIDATION
    db_job.state = engine_models.StateChoice.NEW
    db_job.status = engine_models.StatusChoice.VALIDATION
    db_job.update_assignee(db_people.reviewer_id)
    db_job.save(
        update_fields=[
            "stage",
            "state",
            "status",
            "assignee",
            "assignee_updated_date",
            "updated_date",
        ]
    )

    return db_job


def annotator_of(db_job: engine_models.Job) -> int | None:
    people = get_people(db_job)
    return people.annotator.id if people.annotator else None


def remember_people(db_job: engine_models.Job) -> None:
    "Saves who annotated and who reviewed a job before it leaves their hands"

    copy_people(db_job, db_job)


def copy_people(db_job: engine_models.Job, db_new_job: engine_models.Job) -> None:
    "Gives a job made from another one the same annotator and reviewer"

    people = get_people(db_job)
    JobPeople.objects.update_or_create(
        job=db_new_job,
        defaults={"annotator": people.annotator, "reviewer": people.reviewer},
    )
