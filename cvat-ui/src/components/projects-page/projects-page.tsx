// Copyright (C) 2020-2022 Intel Corporation
// Copyright (C) CVAT.ai Corporation
//
// SPDX-License-Identifier: MIT

import './styles.scss';
import React, {
    useCallback, useEffect, useMemo, useState,
} from 'react';
import { useHistory } from 'react-router';
import { useDispatch, useSelector } from 'react-redux';
import { shallowEqual } from 'utils/redux';
import Spin from 'antd/lib/spin';
import Text from 'antd/lib/typography/Text';
import { CombinedState, ProjectsQuery, SelectedResourceType } from 'reducers';
import { getProjectsAsync, setProjectFolderScope } from 'actions/projects-actions';
import { getMyOrganizationRole } from 'components/job-workflow/api';
import { updateHistoryFromQuery } from 'components/resource-sorting-filtering';
import { anySearch } from 'utils/any-search';
import { useResourceQuery } from 'utils/hooks';
import { selectionActions } from 'actions/selection-actions';
import EmptyListComponent from './empty-list';
import TopBarComponent from './top-bar';
import ProjectListComponent from './project-list';
import ProjectFolderBar, { ProjectFolder, ProjectFoldersContext, foldersApi } from './project-folders';

function folderFromUrl(): number | null {
    const value = new URLSearchParams(window.location.search).get('folder');
    return value && /^\d+$/.test(value) ? Number(value) : null;
}

export default function ProjectsPageComponent(): JSX.Element {
    const dispatch = useDispatch();
    const history = useHistory();
    const {
        fetching,
        count,
        query,
        tasksQuery,
        importing,
        bulkFetching,
        currentProjects,
        deletedProjects,
        selectedCount,
    } = useSelector((state: CombinedState) => ({
        fetching: state.projects.fetching,
        count: state.projects.current.length,
        query: state.projects.gettingQuery,
        tasksQuery: state.projects.tasksGettingQuery,
        importing: state.import.projects.backup.importing,
        bulkFetching: state.bulkActions.fetching,
        currentProjects: state.projects.current,
        deletedProjects: state.projects.activities.deletes,
        selectedCount: state.projects.selected.length,
    }), shallowEqual);
    const selectedIds = useSelector((state: CombinedState) => state.projects.selected as number[]);
    const user = useSelector((state: CombinedState) => state.auth.user);
    const organization = useSelector((state: CombinedState) => state.organizations.current);

    // Folders: the page shows the projects in one folder, or those in no folder
    const [folderId, setFolderId] = useState<number | null>(() => {
        const initial = folderFromUrl();
        setProjectFolderScope(initial);
        return initial;
    });
    const [folders, setFolders] = useState<ProjectFolder[]>([]);
    const [canOrganise, setCanOrganise] = useState(false);
    const currentFolder = folders.find((folder) => folder.id === folderId) ?? null;

    const loadFolders = useCallback((): void => {
        foldersApi.list().then(setFolders).catch(() => setFolders([]));
    }, []);

    useEffect(() => {
        loadFolders();
        return () => setProjectFolderScope(undefined);
    }, [organization]);

    // Maintainers and owners organise the organisation's folders; outside an organisation, everyone their own
    useEffect(() => {
        if (!user) return;
        if (user.isSuperuser || !organization) {
            setCanOrganise(true);
            return;
        }
        getMyOrganizationRole(user.username)
            .then((role) => setCanOrganise(role === 'maintainer' || role === 'owner'))
            .catch(() => setCanOrganise(false));
    }, [user, organization]);

    const openFolder = (folder: ProjectFolder | null): void => {
        const id = folder ? folder.id : null;
        setFolderId(id);
        setProjectFolderScope(id);
        dispatch(selectionActions.clearSelectedResources());
        dispatch(getProjectsAsync({ ...query, page: 1 }, { ...tasksQuery, page: 1 }));
    };

    const onFoldersChanged = (): void => {
        loadFolders();
        dispatch(selectionActions.clearSelectedResources());
        dispatch(getProjectsAsync({ ...query }, tasksQuery));
    };

    const foldersContext = useMemo(() => ({ canOrganise, selectedIds }), [canOrganise, selectedIds]);
    const [isMounted, setIsMounted] = useState(false);
    const isAnySearch = anySearch<ProjectsQuery>(query);

    const selectableProjectIds = currentProjects
        .map((p) => p.id).filter((id) => !deletedProjects[id]);
    const onSelectAll = useCallback(() => {
        dispatch(selectionActions.selectResources(selectableProjectIds, SelectedResourceType.PROJECTS));
    }, [selectableProjectIds]);

    const updatedQuery = useResourceQuery<ProjectsQuery>(query, { pageSize: 12 });

    useEffect(() => {
        dispatch(getProjectsAsync({ ...updatedQuery }));
        setIsMounted(true);
    }, []);

    useEffect(() => {
        if (isMounted) {
            const search = new URLSearchParams(updateHistoryFromQuery(query));
            if (folderId !== null) search.set('folder', String(folderId));
            history.replace({ search: search.toString() });
        }
    }, [query, folderId]);

    let content = count ? <ProjectListComponent /> : <EmptyListComponent notFound={isAnySearch} />;
    if (!count && folderId !== null && !isAnySearch) {
        content = (
            <div className='cvat-empty-project-list'>
                <Text type='secondary'>This folder is empty. Drag projects onto it from All projects.</Text>
            </div>
        );
    }

    return (
        <div className='cvat-projects-page'>
            <TopBarComponent
                onApplySearch={(search: string | null) => {
                    dispatch(
                        getProjectsAsync({
                            ...query,
                            search,
                            page: 1,
                        }, { ...tasksQuery, page: 1 }),
                    );
                }}
                onApplyFilter={(filter: string | null) => {
                    dispatch(
                        getProjectsAsync({
                            ...query,
                            filter,
                            page: 1,
                        }, { ...tasksQuery, page: 1 }),
                    );
                }}
                onApplySorting={(sorting: string | null) => {
                    dispatch(
                        getProjectsAsync({
                            ...query,
                            sort: sorting,
                            page: 1,
                        }, { ...tasksQuery, page: 1 }),
                    );
                }}
                query={updatedQuery}
                importing={importing}
                selectedCount={selectedCount}
                onSelectAll={onSelectAll}
            />
            <ProjectFolderBar
                folders={folders}
                current={currentFolder ?? (folderId !== null ? {
                    id: folderId, name: 'Folder', project_count: count,
                } : null)}
                canOrganise={canOrganise}
                onOpen={openFolder}
                onChanged={onFoldersChanged}
            />
            { fetching && !bulkFetching ? (
                <div className='cvat-empty-project-list'>
                    <Spin size='large' className='cvat-spinner' />
                </div>
            ) : (
                <ProjectFoldersContext.Provider value={foldersContext}>
                    {content}
                </ProjectFoldersContext.Provider>
            )}
        </div>
    );
}
