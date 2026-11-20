import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { Quiz } from '../pages/Quiz';
import { quizApi } from '../api/quiz';

vi.mock('../api/quiz', () => ({
  quizApi: {
    getQuiz: vi.fn(),
    startAttempt: vi.fn(),
    submitQuestionResponse: vi.fn(),
    submitAttempt: vi.fn(),
  },
}));

describe('Quiz Component - Interactive One-by-One Flow', () => {
  const mockQuiz = {
    id: 'quiz-123',
    title: 'Networking & SQL Assessment',
    time_limit_seconds: 600,
    questions: [
      {
        id: 'q-1',
        position: 1,
        type: 'mcq',
        difficulty: 'medium',
        topic: 'RIP Routing',
        question: 'What is the maximum hop count in RIP?',
        options: ['15', '16', '30', 'infinity'],
      },
      {
        id: 'q-2',
        position: 2,
        type: 'true_false',
        difficulty: 'easy',
        topic: 'OSPF Links',
        question: 'True or False: A stub link is connected to only one router.',
        options: ['True', 'False'],
      },
      {
        id: 'q-3',
        position: 3,
        type: 'fill_blank',
        difficulty: 'medium',
        topic: 'SQL Security',
        question: 'Fill in the blank: The ___ statement confers authorizations.',
        options: [],
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    quizApi.getQuiz.mockResolvedValue(mockQuiz);
    quizApi.startAttempt.mockResolvedValue({ id: 'attempt-456' });
  });

  it('renders one question at a time with progress bar and navigation', async () => {
    render(
      <MemoryRouter initialEntries={['/quizzes/quiz-123']}>
        <Routes>
          <Route path="/quizzes/:id" element={<Quiz />} />
        </Routes>
      </MemoryRouter>
    );

    // Initial load: displays Question 1 of 3
    expect(await screen.findByText(/Question 1 of 3/i)).toBeInTheDocument();
    expect(screen.getByText('What is the maximum hop count in RIP?')).toBeInTheDocument();
    expect(screen.queryByText('True or False: A stub link is connected to only one router.')).not.toBeInTheDocument();

    // 4 MCQ options rendered
    expect(screen.getByText('15')).toBeInTheDocument();
    expect(screen.getByText('16')).toBeInTheDocument();
  });

  it('evaluates MCQ instantly, shows explanation, locks options, and enables Next', async () => {
    quizApi.submitQuestionResponse.mockResolvedValue({
      is_correct: true,
      score: 1.0,
      correct_answer: '15',
      explanation: 'In RIP, 15 is the maximum valid hop count.',
      feedback: 'Correct! 15 is the maximum hop count.',
    });

    render(
      <MemoryRouter initialEntries={['/quizzes/quiz-123']}>
        <Routes>
          <Route path="/quizzes/:id" element={<Quiz />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('What is the maximum hop count in RIP?');

    // Click option "15"
    const optionBtn = screen.getByText('15');
    fireEvent.click(optionBtn);

    await waitFor(() => {
      expect(quizApi.submitQuestionResponse).toHaveBeenCalledWith(
        'attempt-456',
        'q-1',
        '15',
        false
      );
    });

    // Verification feedback displayed
    expect(await screen.findByText(/Correct!/i)).toBeInTheDocument();
    expect(screen.getByText(/In RIP, 15 is the maximum valid hop count./i)).toBeInTheDocument();

    // Next button advances to Question 2
    const nextBtn = screen.getByRole('button', { name: /Next Question/i });
    fireEvent.click(nextBtn);

    expect(await screen.findByText(/Question 2 of 3/i)).toBeInTheDocument();
    expect(screen.getByText('True or False: A stub link is connected to only one router.')).toBeInTheDocument();
  });

  it('renders True/False with exactly two buttons', async () => {
    render(
      <MemoryRouter initialEntries={['/quizzes/quiz-123']}>
        <Routes>
          <Route path="/quizzes/:id" element={<Quiz />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText(/Question 1 of 3/i);

    // Click navigator button for question 2
    const navBtn2 = screen.getByTitle('Question 2: OSPF Links');
    fireEvent.click(navBtn2);

    expect(await screen.findByText(/Question 2 of 3/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /True/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /False/i })).toBeInTheDocument();
    // Verify no 4 options
    const choiceButtons = screen.getAllByRole('button').filter(
      (btn) => btn.textContent.includes('True') || btn.textContent.includes('False')
    );
    expect(choiceButtons).toHaveLength(2);
  });

  it('renders Fill-in-the-blank with text input and Check Answer button', async () => {
    quizApi.submitQuestionResponse.mockResolvedValue({
      is_correct: true,
      score: 1.0,
      correct_answer: 'GRANT',
      explanation: 'GRANT statement confers privileges in SQL.',
    });

    render(
      <MemoryRouter initialEntries={['/quizzes/quiz-123']}>
        <Routes>
          <Route path="/quizzes/:id" element={<Quiz />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText(/Question 1 of 3/i);

    // Jump to Question 3
    const navBtn3 = screen.getByTitle('Question 3: SQL Security');
    fireEvent.click(navBtn3);

    expect(await screen.findByText(/Question 3 of 3/i)).toBeInTheDocument();
    const input = screen.getByPlaceholderText(/Type the exact missing term/i);
    expect(input).toBeInTheDocument();

    fireEvent.change(input, { target: { value: 'grant' } });
    const checkBtn = screen.getByRole('button', { name: /Check Answer/i });
    fireEvent.click(checkBtn);

    await waitFor(() => {
      expect(quizApi.submitQuestionResponse).toHaveBeenCalledWith(
        'attempt-456',
        'q-3',
        'grant',
        false
      );
    });

    expect(await screen.findByText(/GRANT statement confers privileges/i)).toBeInTheDocument();
  });
});
