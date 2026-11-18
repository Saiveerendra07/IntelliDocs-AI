import apiClient from './client';

export const chatApi = {
  listConversations: async () => {
    const response = await apiClient.get('/chat/conversations');
    return response.data;
  },
  createConversation: async (data) => {
    const response = await apiClient.post('/chat/conversations', data);
    return response.data;
  },
  getMessages: async (conversationId) => {
    const response = await apiClient.get(`/chat/conversations/${conversationId}/messages`);
    return response.data;
  },
  askQuestion: async (conversationId, payload) => {
    const response = await apiClient.post(`/chat/conversations/${conversationId}/ask`, payload);
    return response.data;
  },
  deleteConversation: async (conversationId) => {
    const response = await apiClient.delete(`/chat/conversations/${conversationId}`);
    return response.data;
  },
};
