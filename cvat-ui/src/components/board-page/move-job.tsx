// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React, { useEffect, useState } from 'react';
import Modal from 'antd/lib/modal';
import Text from 'antd/lib/typography/Text';
import notification from 'antd/lib/notification';

import { Job, JobStage, JobState } from 'cvat-core-wrapper';
import {
    UserOption, displayName, getJobPeople, sendToReview, setJobPeople,
} from 'components/job-workflow/api';
import UserSelect from 'components/job-workflow/user-select';

export type BoardColumnKey = 'unassigned' | 'annotating' | 'review' | 'accepted';

// The column a job is in now, using the same rules as the board's column filters
export function columnOf(job: Job): BoardColumnKey {
    if (job.stage === JobStage.VALIDATION) return 'review';
    if (job.stage === JobStage.ACCEPTANCE) return 'accepted';
    return job.assignee ? 'annotating' : 'unassigned';
}

// Columns that need a person chosen before the move
export const NEEDS_PERSON: Partial<Record<BoardColumnKey, 'annotator' | 'reviewer'>> = {
    annotating: 'annotator',
    review: 'reviewer',
};

const TITLES: Record<BoardColumnKey, string> = {
    unassigned: 'Unassigned',
    annotating: 'Annotating',
    review: 'Review',
    accepted: 'Accepted',
};

function errorText(error: unknown): string {
    return error instanceof Error ? error.message : String(error);
}

export async function moveJob(job: Job, target: BoardColumnKey, person: UserOption | null): Promise<string> {
    switch (target) {
        case 'unassigned':
            await job.save({ stage: JobStage.ANNOTATION, state: JobState.NEW, assignee: null });
            return `Job ${job.id} is unassigned`;
        case 'annotating': {
            if (!person) throw new Error('Choose who annotates it');
            if (job.stage !== JobStage.ANNOTATION) {
                await job.save({ stage: JobStage.ANNOTATION, state: JobState.IN_PROGRESS });
            }
            await setJobPeople(job.id, { annotator: person.id });
            return `Job ${job.id} is with ${displayName(person)} for annotation`;
        }
        case 'review':
            if (job.stage === JobStage.ANNOTATION) {
                // Keeps whoever had the job as its annotator
                await sendToReview(job.id, person ? person.id : null);
            } else {
                // Keep the annotator and reviewer on record before the stage changes
                await setJobPeople(job.id, {}).catch(() => null);
                await job.save({ stage: JobStage.VALIDATION, state: JobState.NEW });
                await setJobPeople(job.id, { reviewer: person ? person.id : null });
            }
            return person ?
                `Job ${job.id} is with ${displayName(person)} for review` :
                `Job ${job.id} is waiting for review`;
        case 'accepted':
            await setJobPeople(job.id, {}).catch(() => null);
            await job.save({ stage: JobStage.ACCEPTANCE, state: JobState.COMPLETED });
            return `Job ${job.id} is accepted`;
        default:
            throw new Error(`Unknown column ${target}`);
    }
}

interface Props {
    job: Job;
    target: BoardColumnKey;
    onClose: () => void;
    onDone: () => void;
}

// Asks who should get the job when it is dropped on Annotating or Review, then moves it
export function MoveJobModal({
    job, target, onClose, onDone,
}: Readonly<Props>): JSX.Element {
    const role = NEEDS_PERSON[target] as 'annotator' | 'reviewer';
    const [person, setPerson] = useState<UserOption | null>(null);
    const [busy, setBusy] = useState(false);

    useEffect(() => {
        getJobPeople([job.id])
            .then((found) => setPerson(found[job.id]?.[role] ?? null))
            .catch(() => setPerson(null));
    }, [job.id]);

    const onOk = async (): Promise<void> => {
        setBusy(true);
        try {
            notification.success({ message: await moveJob(job, target, person), className: 'cvat-notification-board-moved' });
            onDone();
        } catch (error: unknown) {
            notification.error({
                message: `Could not move job ${job.id}`,
                description: errorText(error),
                className: 'cvat-notification-board-move-failed',
            });
        } finally {
            setBusy(false);
        }
    };

    return (
        <Modal
            open
            className='cvat-modal-board-move'
            title={`Move job ${job.id} to ${TITLES[target]}`}
            okText='Move'
            okButtonProps={{ loading: busy, disabled: role === 'annotator' && !person }}
            onOk={onOk}
            onCancel={onClose}
            destroyOnClose
        >
            <Text strong>{role === 'annotator' ? 'Annotator' : 'Reviewer'}</Text>
            <div style={{ marginTop: 4 }}>
                <UserSelect
                    className='cvat-board-move-person'
                    placeholder={role === 'annotator' ? 'Choose the annotator' : 'Choose the reviewer (or leave it empty)'}
                    value={person}
                    onChange={setPerson}
                />
            </div>
        </Modal>
    );
}

export { TITLES as COLUMN_TITLES };
