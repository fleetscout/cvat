// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import React, { useCallback } from 'react';
import { useHistory } from 'react-router';
import Card from 'antd/lib/card';
import Text from 'antd/lib/typography/Text';
import dayjs from 'dayjs';

import { Job } from 'cvat-core-wrapper';
import JobStageStateBadges from 'components/job-item/job-status-visuals';
import { JobPeople } from 'components/job-workflow/api';
import JobPeopleBadges from './job-people';

function frameLabel(count: number): string {
    return count === 1 ? '1 frame' : `${count} frames`;
}

interface Props {
    job: Job;
    people: JobPeople | null;
    onChanged: () => void;
    // Set when the user may drag cards between columns
    onDragStart?: (job: Job) => void;
    onDragEnd?: () => void;
}

function BoardCardComponent({
    job, people, onChanged, onDragStart, onDragEnd,
}: Readonly<Props>): JSX.Element {
    const history = useHistory();

    const onClick = useCallback((event: React.MouseEvent): void => {
        const url = `/tasks/${job.taskId}/jobs/${job.id}`;
        if (event.ctrlKey || event.metaKey) {
            window.open(url, '_blank', 'noopener noreferrer');
        } else {
            history.push(url);
        }
    }, [job.id, job.taskId]);

    return (
        <Card
            hoverable
            size='small'
            className={`cvat-board-card${onDragStart ? ' cvat-board-card-draggable' : ''}`}
            onClick={onClick}
            draggable={!!onDragStart}
            onDragStart={onDragStart ? (event: React.DragEvent) => {
                const { dataTransfer } = event;
                dataTransfer.setData('text/plain', String(job.id));
                dataTransfer.effectAllowed = 'move';
                onDragStart(job);
            } : undefined}
            onDragEnd={onDragEnd}
        >
            <Text strong ellipsis={{ tooltip: job.taskName }} className='cvat-board-card-title'>
                {job.taskName ?? `Task ${job.taskId}`}
            </Text>
            <div className='cvat-board-card-meta'>
                <Text type='secondary'>{`Job ${job.id}`}</Text>
                <Text type='secondary'>{frameLabel(job.frameCount ?? job.stopFrame - job.startFrame + 1)}</Text>
            </div>
            <div className='cvat-board-card-status'>
                <JobStageStateBadges stage={job.stage} state={job.state} />
            </div>
            <div className='cvat-board-card-footer'>
                <Text type='secondary'>{dayjs(job.updatedDate).fromNow()}</Text>
                <JobPeopleBadges jobId={job.id} people={people} onChanged={onChanged} />
            </div>
        </Card>
    );
}

export default React.memo(BoardCardComponent);
