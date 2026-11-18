import apiClient from './client';

export const nlpApi = {
  preprocess: async (text) => {
    const response = await apiClient.post('/nlp/preprocess', { text });
    return response.data;
  },
  getDocumentPreprocessing: async (documentId, sampleSize = 500) => {
    const response = await apiClient.get(`/documents/${documentId}/nlp/preprocessing`, {
      params: { sample_size: sampleSize },
    });
    return response.data;
  },
  getPOS: async (documentId, sampleSize = 300) => {
    const response = await apiClient.get(`/documents/${documentId}/nlp/pos`, {
      params: { sample_size: sampleSize },
    });
    return response.data;
  },
  getEntities: async (documentId) => {
    const response = await apiClient.get(`/documents/${documentId}/nlp/entities`);
    return response.data;
  },
  getNgrams: async (documentId, n = 2) => {
    const response = await apiClient.get(`/documents/${documentId}/nlp/ngrams`, {
      params: { n },
    });
    return response.data;
  },
  getWordFrequency: async (documentId, topN = 30) => {
    const response = await apiClient.get(`/documents/${documentId}/nlp/frequency`, {
      params: { top_n: topN },
    });
    return response.data;
  },
  getKeywords: async (documentId) => {
    const response = await apiClient.get(`/documents/${documentId}/nlp/keywords`);
    return response.data;
  },
  getTopics: async (documentId) => {
    const response = await apiClient.get(`/documents/${documentId}/nlp/topics`);
    return response.data;
  },
  searchTerm: async (documentId, term) => {
    const response = await apiClient.get(`/documents/${documentId}/search-term`, {
      params: { term },
    });
    return response.data;
  },
};
