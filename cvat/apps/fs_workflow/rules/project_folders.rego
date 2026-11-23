package project_folders

import rego.v1

import data.utils
import data.organizations

# input: {
#     "scope": <"create"|"list"|"view"|"update"|"delete"|"update:projects">,
#     "auth": { "user": { "id": <num>, "privilege": <...> }, "organization": {...} or null },
#     "resource": { "id": <num>, "owner": { "id": <num> }, "organization": { "id": <num> } or null }
# }
#
# Folders on the projects page. Everyone in the organisation sees them;
# maintainers and owners organise them. Outside an organisation, people
# organise their own.

UPDATE_PROJECTS := "update:projects"

default allow := false

allow if {
    utils.is_admin
}

allow if {
    input.scope == utils.LIST
    utils.is_sandbox
}

allow if {
    input.scope == utils.LIST
    organizations.is_member
}

allow if {
    input.scope == utils.VIEW
    organizations.is_same_org_as_resource_with_perm(organizations.WORKER)
}

allow if {
    input.scope in {utils.CREATE, utils.UPDATE, utils.DELETE, UPDATE_PROJECTS}
    organizations.is_same_org_as_resource_with_perm(organizations.MAINTAINER)
    utils.has_perm(utils.WORKER)
}

allow if {
    input.scope in {utils.CREATE, utils.VIEW, utils.UPDATE, utils.DELETE, UPDATE_PROJECTS}
    utils.is_sandbox
    input.resource.organization == null
    utils.has_perm(utils.WORKER)
    utils.is_resource_owner
}

base_filter := {} if { # Django Q object to filter list of entries
    utils.is_admin
} else := qobject if {
    utils.is_sandbox
    qobject := {"owner_id": input.auth.user.id}
} else := {} if {
    organizations.is_member
}

filter := utils.add_organization_filter(base_filter, ["organization"])
