import apiClient from './client';

export const summariesApi = {
  generate: async (documentId, options) => {
    const response = await apiClient.post(`/documents/${documentId}/summaries/generate`, options);
    return response.data;
  },
  list: async (documentId) => {
    const response = await apiClient.get(`/documents/${documentId}/summaries`);
    return response.data;
  },
  compare: async (documentId, extractiveMethod = 'textrank') => {
    const response = await apiClient.get(`/documents/${documentId}/summaries/compare`, {
      params: { extractive_method: extractiveMethod },
    });
    return response.data;
  },
};
