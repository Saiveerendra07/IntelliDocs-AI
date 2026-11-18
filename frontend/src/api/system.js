import apiClient from './client';

export const systemApi = {
  getHealth: async () => {
    const response = await apiClient.get('/health');
    return response.data;
  },
  getModels: async () => {
    const response = await apiClient.get('/system/models');
    return response.data;
  },
};
