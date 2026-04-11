import type { ModuleDefinition, OnePanelClientLike, PageInput } from '../types.js';

export interface WebsiteSearchInput extends PageInput {
  name?: string;
  websiteGroupId?: number;
  orderBy?: string;
  order?: string;
  operateNode?: string;
}

export interface WebsiteLogReadInput extends PageInput {
  id: number;
  logName: string;
  operateNode?: string;
}

export interface CertificateSearchInput extends PageInput {
  name?: string;
  acmeAccountID?: string;
}

export interface WebsiteCreateInput {
  alias: string;
  type: string;
  webSiteGroupID: number;
  operateNode?: string;
  [key: string]: unknown;
}

export interface WebsiteSslUploadInput {
  type: 'paste' | 'local';
  certificate?: string;
  certificatePath?: string;
  description?: string;
  privateKey?: string;
  privateKeyPath?: string;
  sslID?: number;
  operateNode?: string;
}

export interface WebsiteHttpsUpdateInput {
  websiteId: number;
  enable?: boolean;
  type?: 'existed' | 'auto' | 'manual';
  websiteSSLId?: number;
  httpConfig?: 'HTTPSOnly' | 'HTTPAlso' | 'HTTPToHTTPS';
  httpsPorts?: number[];
  SSLProtocol?: string[];
  algorithm?: string;
  hsts?: boolean;
  hstsIncludeSubDomains?: boolean;
  http3?: boolean;
  certificate?: string;
  certificatePath?: string;
  privateKey?: string;
  privateKeyPath?: string;
  importType?: string;
  operateNode?: string;
}

async function searchWebsites(client: OnePanelClientLike, input: WebsiteSearchInput = {}) {
  return client.request({
    method: 'POST',
    path: '/api/v2/websites/search',
    operateNode: input.operateNode,
    body: {
      page: input.page ?? 1,
      pageSize: input.pageSize ?? 20,
      name: input.name ?? '',
      websiteGroupId: input.websiteGroupId ?? 0,
      orderBy: input.orderBy ?? 'created_at',
      order: input.order ?? 'descending',
    },
  });
}

async function listWebsites(client: OnePanelClientLike) {
  return client.request({
    method: 'GET',
    path: '/api/v2/websites/list',
  });
}

async function getWebsite(client: OnePanelClientLike, input: { id: number }) {
  return client.request({
    method: 'GET',
    path: `/api/v2/websites/${input.id}`,
  });
}

async function getWebsiteConfig(
  client: OnePanelClientLike,
  input: { id: number; type: string },
) {
  return client.request({
    method: 'GET',
    path: `/api/v2/websites/${input.id}/config/${input.type}`,
  });
}

async function listDomains(client: OnePanelClientLike, input: { id: number }) {
  return client.request({
    method: 'GET',
    path: `/api/v2/websites/domains/${input.id}`,
  });
}

async function getHttpsConfig(client: OnePanelClientLike, input: { id: number }) {
  return client.request({
    method: 'GET',
    path: `/api/v2/websites/${input.id}/https`,
  });
}

async function searchCertificates(
  client: OnePanelClientLike,
  input: CertificateSearchInput = {},
) {
  return client.request({
    method: 'POST',
    path: '/api/v2/websites/ssl/search',
    body: {
      page: input.page ?? 1,
      pageSize: input.pageSize ?? 20,
      name: input.name ?? '',
      acmeAccountID: input.acmeAccountID ?? '',
    },
  });
}

async function listCertificates(
  client: OnePanelClientLike,
  input: { name?: string; acmeAccountID?: string } = {},
) {
  return client.request({
    method: 'POST',
    path: '/api/v2/websites/ssl/list',
    body: {
      name: input.name ?? '',
      acmeAccountID: input.acmeAccountID ?? '',
    },
  });
}

async function getCertificate(client: OnePanelClientLike, input: { id: number }) {
  return client.request({
    method: 'GET',
    path: `/api/v2/websites/ssl/${input.id}`,
  });
}

async function readWebsiteLogLines(
  client: OnePanelClientLike,
  input: WebsiteLogReadInput,
) {
  return client.request({
    method: 'POST',
    path: '/api/v2/files/read',
    operateNode: input.operateNode,
    body: {
      id: input.id,
      type: 'website',
      name: input.logName,
      page: input.page ?? 1,
      pageSize: input.pageSize ?? 200,
    },
  });
}

async function createWebsite(client: OnePanelClientLike, input: WebsiteCreateInput) {
  const { operateNode, ...body } = input;
  return client.request({
    method: 'POST',
    path: '/api/v2/websites',
    operateNode,
    body,
  });
}

async function uploadWebsiteSsl(
  client: OnePanelClientLike,
  input: WebsiteSslUploadInput,
) {
  const { operateNode, ...body } = input;
  return client.request({
    method: 'POST',
    path: '/api/v2/websites/ssl/upload',
    operateNode,
    body,
  });
}

async function updateWebsiteHttps(
  client: OnePanelClientLike,
  input: WebsiteHttpsUpdateInput,
) {
  const { operateNode, websiteId, ...body } = input;
  return client.request({
    method: 'POST',
    path: `/api/v2/websites/${websiteId}/https`,
    operateNode,
    body: {
      websiteId,
      ...body,
    },
  });
}

export const websitesModule: ModuleDefinition = {
  id: 'websites',
  title: 'Websites',
  description: 'Website list/detail reads, HTTPS and certificate reads, and website log reads.',
  actions: {
    searchWebsites: {
      id: 'searchWebsites',
      summary: 'Read paginated website rows and status fields.',
      method: 'POST',
      path: '/api/v2/websites/search',
      nodeAware: true,
      execute: searchWebsites,
    },
    listWebsites: {
      id: 'listWebsites',
      summary: 'Read simple website options.',
      method: 'GET',
      path: '/api/v2/websites/list',
      execute: (client) => listWebsites(client),
    },
    getWebsite: {
      id: 'getWebsite',
      summary: 'Read one website detail, including runtime and log-path metadata.',
      method: 'GET',
      path: '/api/v2/websites/:id',
      execute: getWebsite,
    },
    getWebsiteConfig: {
      id: 'getWebsiteConfig',
      summary: 'Read one website config file by config type.',
      method: 'GET',
      path: '/api/v2/websites/:id/config/:type',
      execute: getWebsiteConfig,
    },
    listDomains: {
      id: 'listDomains',
      summary: 'Read the domains bound to a website.',
      method: 'GET',
      path: '/api/v2/websites/domains/:id',
      execute: listDomains,
    },
    getHttpsConfig: {
      id: 'getHttpsConfig',
      summary: 'Read HTTPS config for one website.',
      method: 'GET',
      path: '/api/v2/websites/:id/https',
      execute: getHttpsConfig,
    },
    searchCertificates: {
      id: 'searchCertificates',
      summary: 'Read paginated SSL certificate rows.',
      method: 'POST',
      path: '/api/v2/websites/ssl/search',
      execute: searchCertificates,
    },
    listCertificates: {
      id: 'listCertificates',
      summary: 'Read SSL certificate options.',
      method: 'POST',
      path: '/api/v2/websites/ssl/list',
      execute: listCertificates,
    },
    getCertificate: {
      id: 'getCertificate',
      summary: 'Read one SSL certificate in detail.',
      method: 'GET',
      path: '/api/v2/websites/ssl/:id',
      execute: getCertificate,
    },
    readWebsiteLogLines: {
      id: 'readWebsiteLogLines',
      summary: 'Read website log lines through the generic file-log endpoint. Common names are access.log and error.log.',
      method: 'POST',
      path: '/api/v2/files/read',
      nodeAware: true,
      execute: readWebsiteLogLines,
    },
    createWebsite: {
      id: 'createWebsite',
      summary: 'Create one website object, including proxy sites backed by an installed OpenResty app.',
      method: 'POST',
      path: '/api/v2/websites',
      nodeAware: true,
      execute: createWebsite,
    },
    uploadWebsiteSsl: {
      id: 'uploadWebsiteSsl',
      summary: 'Upload an existing certificate and key into the 1Panel website SSL store.',
      method: 'POST',
      path: '/api/v2/websites/ssl/upload',
      nodeAware: true,
      execute: uploadWebsiteSsl,
    },
    updateWebsiteHttps: {
      id: 'updateWebsiteHttps',
      summary: 'Bind HTTPS settings and a stored certificate to one website.',
      method: 'POST',
      path: '/api/v2/websites/:id/https',
      nodeAware: true,
      execute: updateWebsiteHttps,
    },
  },
  reservedMutations: [
    {
      id: 'updateWebsite',
      method: 'POST',
      path: '/api/v2/websites/update',
      note: 'Reserved for future website updates.',
    },
    {
      id: 'operateWebsite',
      method: 'POST',
      path: '/api/v2/websites/operate',
      note: 'Reserved for start/stop/restart operations.',
    },
    {
      id: 'deleteWebsite',
      method: 'POST',
      path: '/api/v2/websites/del',
      note: 'Reserved for future deletion.',
    },
    {
      id: 'updateCertificate',
      method: 'POST',
      path: '/api/v2/websites/ssl/update',
      note: 'Reserved for SSL mutations.',
    },
  ],
};
