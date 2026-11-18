import apiClient from './client';

export const flashcardsApi = {
  list: async (documentId = null) => {
    const params = documentId ? { document_id: documentId } : {};
    const response = await apiClient.get('/flashcards', { params });
    return response.data;
  },
  generate: async (documentId) => {
    const response = await apiClient.post('/flashcards/generate', { document_id: documentId });
    return response.data;
  },
  review: async (flashcardId, difficulty) => {
    const response = await apiClient.patch(`/flashcards/${flashcardId}/review`, {
      difficulty_mark: difficulty,
    });
    return response.data;
  },
};
