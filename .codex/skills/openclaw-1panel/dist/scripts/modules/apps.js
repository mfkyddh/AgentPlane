async function searchInstalledApps(client, input = {}) {
    return client.request({
        method: 'POST',
        path: '/api/v2/apps/installed/search',
        operateNode: input.operateNode,
        body: {
            page: input.page ?? 1,
            pageSize: input.pageSize ?? 20,
            name: input.name ?? '',
            type: input.type ?? '',
            unused: input.unused ?? false,
            all: input.all ?? false,
        },
    });
}
async function listInstalledApps(client) {
    return client.request({
        method: 'GET',
        path: '/api/v2/apps/installed/list',
    });
}
async function getInstalledApp(client, input) {
    return client.request({
        method: 'GET',
        path: `/api/v2/apps/installed/info/${input.installId}`,
        operateNode: input.operateNode,
    });
}
async function searchCatalog(client, input = {}) {
    return client.request({
        method: 'POST',
        path: '/api/v2/apps/search',
        body: {
            page: input.page ?? 1,
            pageSize: input.pageSize ?? 20,
            name: input.name ?? '',
            tags: input.tags ?? [],
            type: input.type ?? '',
            recommend: input.recommend ?? false,
            resource: input.resource ?? '',
            showCurrentArch: input.showCurrentArch ?? true,
        },
    });
}
async function getAppByKey(client, input) {
    return client.request({
        method: 'GET',
        path: `/api/v2/apps/${input.key}`,
        operateNode: input.operateNode,
    });
}
async function getAppDetail(client, input) {
    return client.request({
        method: 'GET',
        path: `/api/v2/apps/detail/${input.appId}/${input.version}/${input.type}`,
        operateNode: input.operateNode,
    });
}
async function getAppServices(client, input) {
    return client.request({
        method: 'GET',
        path: `/api/v2/apps/services/${input.key}`,
        operateNode: input.operateNode,
    });
}
async function getAppPort(client, input) {
    return client.request({
        method: 'POST',
        path: '/api/v2/apps/installed/loadport',
        body: input,
    });
}
async function getAppConnInfo(client, input) {
    return client.request({
        method: 'POST',
        path: '/api/v2/apps/installed/conninfo',
        body: input,
    });
}
async function installApp(client, input) {
    const { operateNode, ...body } = input;
    return client.request({
        method: 'POST',
        path: '/api/v2/apps/install',
        operateNode,
        body,
    });
}
async function updateAppInstallParams(client, input) {
    const { operateNode, ...body } = input;
    return client.request({
        method: 'POST',
        path: '/api/v2/apps/installed/params/update',
        operateNode,
        body,
    });
}
export const appsModule = {
    id: 'apps',
    title: 'Apps',
    description: 'App catalog reads, installed app inspection, service reads, and status checks.',
    actions: {
        searchInstalledApps: {
            id: 'searchInstalledApps',
            summary: 'Read installed apps with status and version fields.',
            method: 'POST',
            path: '/api/v2/apps/installed/search',
            nodeAware: true,
            execute: searchInstalledApps,
        },
        listInstalledApps: {
            id: 'listInstalledApps',
            summary: 'Read simple installed-app options.',
            method: 'GET',
            path: '/api/v2/apps/installed/list',
            execute: (client) => listInstalledApps(client),
        },
        getInstalledApp: {
            id: 'getInstalledApp',
            summary: 'Read one installed app detail.',
            method: 'GET',
            path: '/api/v2/apps/installed/info/:installId',
            nodeAware: true,
            execute: getInstalledApp,
        },
        searchCatalog: {
            id: 'searchCatalog',
            summary: 'Read app catalog entries.',
            method: 'POST',
            path: '/api/v2/apps/search',
            execute: searchCatalog,
        },
        getAppByKey: {
            id: 'getAppByKey',
            summary: 'Read one app catalog entry by app key.',
            method: 'GET',
            path: '/api/v2/apps/:key',
            nodeAware: true,
            execute: getAppByKey,
        },
        getAppDetail: {
            id: 'getAppDetail',
            summary: 'Read one app version detail.',
            method: 'GET',
            path: '/api/v2/apps/detail/:appId/:version/:type',
            nodeAware: true,
            execute: getAppDetail,
        },
        getAppServices: {
            id: 'getAppServices',
            summary: 'Read service definitions for an app key.',
            method: 'GET',
            path: '/api/v2/apps/services/:key',
            nodeAware: true,
            execute: getAppServices,
        },
        getAppPort: {
            id: 'getAppPort',
            summary: 'Read the externally exposed port for an installed app.',
            method: 'POST',
            path: '/api/v2/apps/installed/loadport',
            execute: getAppPort,
        },
        getAppConnInfo: {
            id: 'getAppConnInfo',
            summary: 'Read connection info for an installed app or app-backed service.',
            method: 'POST',
            path: '/api/v2/apps/installed/conninfo',
            execute: getAppConnInfo,
        },
        installApp: {
            id: 'installApp',
            summary: 'Install one app or runtime with a validated app detail and install params.',
            method: 'POST',
            path: '/api/v2/apps/install',
            nodeAware: true,
            execute: installApp,
        },
        updateAppInstallParams: {
            id: 'updateAppInstallParams',
            summary: 'Update install parameters for an existing app or runtime without using destructive operations.',
            method: 'POST',
            path: '/api/v2/apps/installed/params/update',
            nodeAware: true,
            execute: updateAppInstallParams,
        },
    },
    reservedMutations: [
        {
            id: 'operateInstalledApp',
            method: 'POST',
            path: '/api/v2/apps/installed/op',
            note: 'Reserved for start/stop/restart/delete/upgrade operations.',
        },
    ],
};
