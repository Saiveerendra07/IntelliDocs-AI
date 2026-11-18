import apiClient from './client';

export const authApi = {
  login: async (credentials) => {
    // Standard OAuth2 password request form or JSON
    const response = await apiClient.post('/auth/login', credentials);
    return response.data;
  },
  register: async (userData) => {
    const response = await apiClient.post('/auth/register', userData);
    return response.data;
  },
  getMe: async () => {
    const response = await apiClient.get('/users/me');
    return response.data;
  },
  updateProfile: async (data) => {
    const response = await apiClient.patch('/users/me', data);
    return response.data;
  },
  changePassword: async (data) => {
    const response = await apiClient.post('/users/me/password', data);
    return response.data;
  },
};
