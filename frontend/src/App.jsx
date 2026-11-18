import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';

import { AuthProvider } from './context/AuthContext';
import { ThemeProvider } from './context/ThemeContext';
import { DashboardLayout } from './layouts/DashboardLayout';
import { ProtectedRoute } from './components/common/ProtectedRoute';

import { Login } from './pages/Login';
import { Signup } from './pages/Signup';
import { Dashboard } from './pages/Dashboard';
import { Upload } from './pages/Upload';
import { DocumentLibrary } from './pages/DocumentLibrary';
import { DocumentDetails } from './pages/DocumentDetails';
import { Summarize } from './pages/Summarize';
import { NLPAnalysis } from './pages/NLPAnalysis';
import { Chat } from './pages/Chat';
import { QuestionGen } from './pages/QuestionGen';
import { Quiz } from './pages/Quiz';
import { QuizResults } from './pages/QuizResults';
import { Flashcards } from './pages/Flashcards';
import { Analytics } from './pages/Analytics';
import { Settings } from './pages/Settings';
import { NotFound } from './pages/NotFound';

export default function App() {
  return (
    <ThemeProvider>
      <AuthProvider>
        <BrowserRouter>
          <Toaster position="top-right" />
          <Routes>
            {/* Public Auth Routes */}
            <Route path="/login" element={<Login />} />
            <Route path="/signup" element={<Signup />} />

            {/* Protected App Routes */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <DashboardLayout />
                </ProtectedRoute>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="upload" element={<Upload />} />
              <Route path="documents" element={<DocumentLibrary />} />
              <Route path="documents/:id" element={<DocumentDetails />} />
              <Route path="summaries" element={<Summarize />} />
              <Route path="nlp" element={<NLPAnalysis />} />
              <Route path="chat" element={<Chat />} />
              <Route path="questions" element={<QuestionGen />} />
              <Route path="quizzes" element={<QuestionGen />} />
              <Route path="quizzes/:id" element={<Quiz />} />
              <Route path="attempts/:id/results" element={<QuizResults />} />
              <Route path="flashcards" element={<Flashcards />} />
              <Route path="analytics" element={<Analytics />} />
              <Route path="settings" element={<Settings />} />
              <Route path="*" element={<NotFound />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </AuthProvider>
    </ThemeProvider>
  );
}
