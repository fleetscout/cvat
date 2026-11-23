// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

// Folders on the projects page (FleetScout). Projects dragged into a folder leave the main list.

import React, { createContext, useContext, useState } from 'react';
import Button from 'antd/lib/button';
import Input from 'antd/lib/input';
import Modal from 'antd/lib/modal';
import Text from 'antd/lib/typography/Text';
import notification from 'antd/lib/notification';
import {
    ArrowLeftOutlined, DeleteOutlined, EditOutlined, FolderAddOutlined, FolderOutlined,
} from '@ant-design/icons';

import { Row, Col } from 'antd/lib/grid';
import { getCore } from 'cvat-core-wrapper';
import dimensions from 'utils/dimensions';

const core = getCore();
const DRAG_TYPE = 'application/x-cvat-projects';

export interface ProjectFolder {
    id: number;
    name: string;
    project_count: number;
}

function url(path: string): string {
    return `${core.config.backendAPI}${path}`;
}

async function call<T>(path: string, method: string, data?: object): Promise<T> {
    const response = await core.server.request(url(path), { method, data }) as { data: T };
    return response.data;
}

export const foldersApi = {
    list: () => call<ProjectFolder[]>('/project_folders', 'GET'),
    create: (name: string) => call<ProjectFolder>('/project_folders', 'POST', { name }),
    rename: (id: number, name: string) => call<ProjectFolder>(`/project_folders/${id}`, 'PATCH', { name }),
    remove: (id: number) => call<void>(`/project_folders/${id}`, 'DELETE'),
    add: (id: number, projects: number[]) => call<ProjectFolder>(
        `/project_folders/${id}/add_projects`, 'POST', { projects },
    ),
    takeOut: (id: number, projects: number[]) => call<ProjectFolder>(
        `/project_folders/${id}/remove_projects`, 'POST', { projects },
    ),
};

// Lets project cards know whether they can be dragged into folders
export const ProjectFoldersContext = createContext<{ canOrganise: boolean; selectedIds: number[] }>({
    canOrganise: false, selectedIds: [],
});

export function useProjectDrag(projectId: number): Partial<React.HTMLAttributes<HTMLDivElement>> {
    const { canOrganise, selectedIds } = useContext(ProjectFoldersContext);
    if (!canOrganise) return {};
    return {
        draggable: true,
        onDragStart: (event: React.DragEvent) => {
            // Dragging a selected card moves every selected project
            const ids = selectedIds.includes(projectId) ? selectedIds : [projectId];
            const { dataTransfer } = event;
            dataTransfer.setData(DRAG_TYPE, JSON.stringify(ids));
            dataTransfer.setData('text/plain', ids.join(','));
            dataTransfer.effectAllowed = 'move';
        },
    };
}

function readDrag(event: React.DragEvent): number[] {
    try {
        return JSON.parse(event.dataTransfer.getData(DRAG_TYPE) || '[]');
    } catch (_error: unknown) {
        return [];
    }
}

function errorText(error: unknown): string {
    return error instanceof Error ? error.message : String(error);
}

interface DropTargetProps {
    className: string;
    enabled: boolean;
    onDropProjects: (ids: number[]) => void;
    onClick?: () => void;
    children: React.ReactNode;
}

function DropTarget({
    className, enabled, onDropProjects, onClick, children,
}: Readonly<DropTargetProps>): JSX.Element {
    const [over, setOver] = useState(false);
    return (
        <div
            role='button'
            tabIndex={0}
            className={`${className}${over ? ' cvat-project-folder-drop-over' : ''}`}
            onClick={onClick}
            onKeyDown={(event) => { if (event.key === 'Enter' && onClick) onClick(); }}
            onDragOver={(event: React.DragEvent) => {
                if (!enabled || !event.dataTransfer.types.includes(DRAG_TYPE)) return;
                event.preventDefault();
                if (!over) setOver(true);
            }}
            onDragLeave={(event: React.DragEvent) => {
                if (!event.currentTarget.contains(event.relatedTarget as Node | null)) setOver(false);
            }}
            onDrop={(event: React.DragEvent) => {
                event.preventDefault();
                setOver(false);
                const ids = readDrag(event);
                if (enabled && ids.length) onDropProjects(ids);
            }}
        >
            {children}
        </div>
    );
}

interface Props {
    folders: ProjectFolder[];
    current: ProjectFolder | null;
    canOrganise: boolean;
    onOpen: (folder: ProjectFolder | null) => void;
    onChanged: () => void;
}

export default function ProjectFolderBar({
    folders, current, canOrganise, onOpen, onChanged,
}: Readonly<Props>): JSX.Element | null {
    const [naming, setNaming] = useState<{ folder: ProjectFolder | null; name: string } | null>(null);

    const run = async (work: () => Promise<unknown>, done: string): Promise<void> => {
        try {
            await work();
            notification.success({ message: done, className: 'cvat-notification-project-folder-done' });
            onChanged();
        } catch (error: unknown) {
            notification.error({
                message: 'Could not change the folders',
                description: errorText(error),
                className: 'cvat-notification-project-folder-failed',
            });
        }
    };

    const moveInto = (folder: ProjectFolder, ids: number[]): Promise<void> => run(
        () => foldersApi.add(folder.id, ids),
        `${ids.length === 1 ? '1 project' : `${ids.length} projects`} moved to ${folder.name}`,
    );

    const takeOut = (ids: number[]): Promise<void> => (current ? run(
        () => foldersApi.takeOut(current.id, ids),
        `${ids.length === 1 ? '1 project' : `${ids.length} projects`} moved back to Projects`,
    ) : Promise.resolve());

    const saveName = (): void => {
        if (!naming) return;
        const name = naming.name.trim();
        if (!name) return;
        const { folder } = naming;
        setNaming(null);
        run(
            () => (folder ? foldersApi.rename(folder.id, name) : foldersApi.create(name)),
            folder ? `Folder renamed to ${name}` : `Folder ${name} created`,
        );
    };

    const confirmDelete = (folder: ProjectFolder): void => {
        Modal.confirm({
            title: `Delete the folder ${folder.name}?`,
            content: `Its ${folder.project_count} project${folder.project_count === 1 ? '' : 's'} go back to the ` +
                'main projects page. No projects are deleted.',
            okText: 'Delete folder',
            className: 'cvat-modal-delete-project-folder',
            onOk: () => run(() => foldersApi.remove(folder.id), `Folder ${folder.name} deleted`)
                .then(() => onOpen(null)),
        });
    };

    if (!folders.length && !canOrganise && !current) return null;

    return (
        <Row justify='center' className='cvat-project-folders'>
            <Col {...dimensions}>
                {current ? (
                    <div className='cvat-project-folders-current'>
                        <DropTarget
                            className='cvat-project-folder-back'
                            enabled={canOrganise}
                            onDropProjects={takeOut}
                            onClick={() => onOpen(null)}
                        >
                            <ArrowLeftOutlined />
                            <span>All projects</span>
                        </DropTarget>
                        <Text strong className='cvat-project-folders-current-name'>
                            <FolderOutlined />
                            {` ${current.name}`}
                        </Text>
                        {canOrganise && (
                            <>
                                <Button
                                    size='small'
                                    icon={<EditOutlined />}
                                    onClick={() => setNaming({ folder: current, name: current.name })}
                                >
                                    Rename
                                </Button>
                                <Button size='small' danger icon={<DeleteOutlined />} onClick={() => confirmDelete(current)}>
                                    Delete folder
                                </Button>
                                <Text type='secondary'>Drag projects onto All projects to take them out.</Text>
                            </>
                        )}
                    </div>
                ) : (
                    <div className='cvat-project-folders-list'>
                        {folders.map((folder) => (
                            <DropTarget
                                key={folder.id}
                                className='cvat-project-folder'
                                enabled={canOrganise}
                                onDropProjects={(ids) => moveInto(folder, ids)}
                                onClick={() => onOpen(folder)}
                            >
                                <FolderOutlined className='cvat-project-folder-icon' />
                                <span className='cvat-project-folder-name'>{folder.name}</span>
                                <span className='cvat-project-folder-count'>{folder.project_count}</span>
                            </DropTarget>
                        ))}
                        {canOrganise && (
                            <Button
                                className='cvat-project-folder-new'
                                icon={<FolderAddOutlined />}
                                onClick={() => setNaming({ folder: null, name: '' })}
                            >
                                New folder
                            </Button>
                        )}
                        {canOrganise && folders.length > 0 && (
                            <Text type='secondary' className='cvat-project-folders-hint'>
                                Drag projects onto a folder to tidy them away. Select several to move them together.
                            </Text>
                        )}
                    </div>
                )}
                {naming && (
                    <Modal
                        open
                        title={naming.folder ? 'Rename folder' : 'New folder'}
                        okText={naming.folder ? 'Rename' : 'Create'}
                        okButtonProps={{ disabled: !naming.name.trim() }}
                        onOk={saveName}
                        onCancel={() => setNaming(null)}
                        className='cvat-modal-project-folder-name'
                        destroyOnClose
                    >
                        <Input
                            autoFocus
                            maxLength={64}
                            placeholder='e.g. Finished projects'
                            value={naming.name}
                            onChange={(event) => setNaming({ ...naming, name: event.target.value })}
                            onPressEnter={saveName}
                        />
                    </Modal>
                )}
            </Col>
        </Row>
    );
}
