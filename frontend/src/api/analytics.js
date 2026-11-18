import apiClient from './client';

export const analyticsApi = {
  getOverview: async () => {
    const response = await apiClient.get('/analytics/overview');
    return response.data;
  },
  getProgress: async () => {
    const response = await apiClient.get('/analytics/progress');
    return response.data;
  },
  getWeakTopics: async () => {
    const response = await apiClient.get('/analytics/weak-topics');
    return response.data;
  },
  getActivity: async () => {
    const response = await apiClient.get('/analytics/activity');
    return response.data;
  },
};
