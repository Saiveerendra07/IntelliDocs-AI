import apiClient from './client';

export const quizApi = {
  generateQuestions: async (config) => {
    const response = await apiClient.post('/questions/generate', config);
    return response.data;
  },
  listQuestions: async (documentId) => {
    const response = await apiClient.get('/questions', { params: { document_id: documentId } });
    return response.data;
  },
  createQuiz: async (quizData) => {
    const response = await apiClient.post('/quizzes', quizData);
    return response.data;
  },
  getQuiz: async (quizId) => {
    const response = await apiClient.get(`/quizzes/${quizId}`);
    return response.data;
  },
  startAttempt: async (quizId) => {
    const response = await apiClient.post(`/quizzes/${quizId}/attempts`);
    return response.data;
  },
  submitAttempt: async (attemptId, answers, timeTaken) => {
    const response = await apiClient.post(`/attempts/${attemptId}/submit`, {
      responses: answers,
      time_taken_seconds: timeTaken,
    });
    return response.data;
  },
  getResults: async (attemptId) => {
    const response = await apiClient.get(`/attempts/${attemptId}/results`);
    return response.data;
  },
};
