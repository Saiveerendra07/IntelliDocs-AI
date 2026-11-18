import apiClient from './client';

export const documentsApi = {
  list: async (params = {}) => {
    const response = await apiClient.get('/documents', { params });
    return response.data;
  },
  getById: async (id) => {
    const response = await apiClient.get(`/documents/${id}`);
    return response.data;
  },
  getStatus: async (id) => {
    const response = await apiClient.get(`/documents/${id}/status`);
    return response.data;
  },
  getPages: async (id, params = {}) => {
    const response = await apiClient.get(`/documents/${id}/pages`, { params });
    return response.data;
  },
  upload: async (formData, onProgress) => {
    const response = await apiClient.post('/documents/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (onProgress && progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress(percent);
        }
      },
    });
    return response.data;
  },
  delete: async (id) => {
    const response = await apiClient.delete(`/documents/${id}`);
    return response.data;
  },
  downloadOriginal: async (id) => {
    const response = await apiClient.get(`/documents/${id}/download`, {
      responseType: 'blob',
    });
    return response.data;
  },
  exportProcessed: async (id, format = 'json') => {
    const response = await apiClient.get(`/documents/${id}/export`, {
      params: { format },
    });
    return response.data;
  },
};
