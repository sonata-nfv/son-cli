/**
 * API Strings to be used for communication.
 */

const HOST_URL = 'http://127.0.0.1';
const HOST_PORT = '5050';
const HOST_ADDRESS = `${HOST_URL}:${HOST_PORT}`;

const API_ENDPOINTS = {
  validate: '/validate',
  report: '/report',
  resources: '/resources',
  watches: '/watches',
};

export const TOKENS = {
  type: '{##object_type}',
  id: '{##id}',
};

export const API = {
  validate: `${HOST_ADDRESS}${API_ENDPOINTS.validate}/${TOKENS.type}`,
  report: {
    list: `${HOST_ADDRESS}${API_ENDPOINTS.report}`,
    single: {
      result: `${HOST_ADDRESS}${API_ENDPOINTS.report}/result/${TOKENS.id}`,
      topology: `${HOST_ADDRESS}${API_ENDPOINTS.report}/topology/${TOKENS.id}`,
      fwgraph: `${HOST_ADDRESS}${API_ENDPOINTS.report}/fwgraph/${TOKENS.id}`,
    },
  },
  resources: `${HOST_ADDRESS}${API_ENDPOINTS.resources}`,
  watches: `${HOST_ADDRESS}${API_ENDPOINTS.watches}`,
};

export default {
  API,
  TOKENS,
};
