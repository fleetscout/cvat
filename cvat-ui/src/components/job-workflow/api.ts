// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Calls for the job workflow actions (split between people, return flagged frames).
// They go through cvat-core so the organisation context and CSRF handling are applied.

import { getCore } from 'cvat-core-wrapper';

const core = getCore();

export interface WorkflowJob {
    id: number;
    task_id: number;
    assignee: { id: number; username: string } | null;
    frame_count?: number;
}

function url(path: string): string {
    return `${core.config.backendAPI}${path}`;
}

export async function splitJobBetween(jobId: number, assigneeIds: number[]): Promise<WorkflowJob[]> {
    const response = await core.server.request(url(`/jobs/${jobId}/split`), {
        method: 'POST',
        data: { assignees: assigneeIds },
    }) as { data: WorkflowJob[] };
    return response.data;
}

export async function returnFlaggedFrames(jobId: number, assigneeId: number | null): Promise<WorkflowJob> {
    const response = await core.server.request(url(`/jobs/${jobId}/return_flagged_frames`), {
        method: 'POST',
        data: assigneeId === null ? {} : { assignee: assigneeId },
    }) as { data: WorkflowJob };
    return response.data;
}

export interface UserOption {
    id: number;
    username: string;
    first_name?: string;
    last_name?: string;
}

export async function searchUsers(search: string): Promise<UserOption[]> {
    const users = await core.users.get({ limit: 20, is_active: true, ...(search ? { search } : {}) });
    return users.map((user: { id: number; username: string; firstName?: string; lastName?: string }) => ({
        id: user.id,
        username: user.username,
        first_name: user.firstName,
        last_name: user.lastName,
    }));
}

export interface JobPeople {
    job_id: number;
    annotator: UserOption | null;
    reviewer: UserOption | null;
}

export async function getJobPeople(jobIds: number[]): Promise<Record<number, JobPeople>> {
    if (!jobIds.length) return {};
    const response = await core.server.request(url('/jobs/people'), {
        method: 'GET',
        params: { ids: jobIds.join(',') },
    }) as { data: JobPeople[] };
    return Object.fromEntries(response.data.map((people) => [people.job_id, people]));
}

export async function setJobPeople(
    jobId: number,
    changes: { annotator?: number | null; reviewer?: number | null },
): Promise<JobPeople> {
    const response = await core.server.request(url(`/jobs/${jobId}/people`), {
        method: 'PATCH',
        data: changes,
    }) as { data: JobPeople };
    return response.data;
}

export async function sendToReview(jobId: number, reviewerId?: number | null): Promise<WorkflowJob> {
    const response = await core.server.request(url(`/jobs/${jobId}/send_to_review`), {
        method: 'POST',
        data: reviewerId === undefined ? {} : { reviewer: reviewerId },
    }) as { data: WorkflowJob };
    return response.data;
}

export function displayName(user: UserOption): string {
    const full = [user.first_name, user.last_name].filter(Boolean).join(' ');
    return full ? `${full} (${user.username})` : user.username;
}

export function initials(user: UserOption): string {
    const parts = [user.first_name, user.last_name].filter((part): part is string => !!part);
    const source = parts.length ? parts : user.username.split(/[._\-\s@]+/).filter(Boolean);
    return source.slice(0, 2).map((part) => part[0].toUpperCase()).join('') || '?';
}

// The signed-in user's role in the current organisation, or null outside one
export async function getMyOrganizationRole(username: string): Promise<string | null> {
    const response = await core.server.request(url('/memberships'), {
        method: 'GET',
        params: { user: username, page_size: 1 },
    }) as { data: { results: { role: string }[] } };
    return response.data.results[0]?.role ?? null;
}
