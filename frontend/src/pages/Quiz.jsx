import React, { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  Clock,
  CheckCircle2,
  Bookmark,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  Award,
} from 'lucide-react';
import { quizApi } from '../api/quiz';

export const Quiz = () => {
  const { id } = useParams();
  const navigate = useNavigate();

  const [quiz, setQuiz] = useState(null);
  const [attemptId, setAttemptId] = useState(null);
  const [questions, setQuestions] = useState([]);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState({}); // { [questionId]: selectedOption }
  const [markedForReview, setMarkedForReview] = useState(new Set());
  const [timeLeft, setTimeLeft] = useState(600); // 10 minutes default
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    const initQuiz = async () => {
      setLoading(true);
      try {
        const quizData = await quizApi.getQuiz(id);
        setQuiz(quizData);
        setQuestions(quizData.questions || []);
        setTimeLeft(quizData.time_limit_seconds || (quizData.questions?.length || 10) * 60);

        // Start attempt
        const attempt = await quizApi.startAttempt(id);
        setAttemptId(attempt.id);
      } catch (err) {
        console.error('Failed to initialize quiz:', err);
      } finally {
        setLoading(false);
      }
    };
    initQuiz();
  }, [id]);

  // Countdown timer
  useEffect(() => {
    if (timeLeft <= 0) {
      handleSubmitQuiz();
      return;
    }
    const timer = setInterval(() => {
      setTimeLeft((prev) => (prev > 0 ? prev - 1 : 0));
    }, 1000);
    return () => clearInterval(timer);
  }, [timeLeft]);

  const currentQ = questions[currentIndex];

  const handleSelectOption = (option) => {
    if (!currentQ) return;
    setAnswers((prev) => ({
      ...prev,
      [currentQ.id]: option,
    }));
  };

  const toggleMarkForReview = () => {
    if (!currentQ) return;
    setMarkedForReview((prev) => {
      const next = new Set(prev);
      if (next.has(currentQ.id)) {
        next.delete(currentQ.id);
      } else {
        next.add(currentQ.id);
      }
      return next;
    });
  };

  const handleSubmitQuiz = async () => {
    if (submitting) return;

    const unansweredCount = questions.length - Object.keys(answers).length;
    if (unansweredCount > 0) {
      const confirm = window.confirm(
        `You have ${unansweredCount} unanswered questions. Are you sure you want to submit?`
      );
      if (!confirm) return;
    }

    setSubmitting(true);
    try {
      const formattedResponses = questions.map((q) => ({
        quiz_question_id: q.id,
        selected_answer: answers[q.id] || null,
        marked_for_review: markedForReview.has(q.id),
      }));

      const timeTaken = (quiz?.time_limit_seconds || 600) - timeLeft;
      const res = await quizApi.submitAttempt(attemptId, formattedResponses, Math.max(timeTaken, 1));
      navigate(`/attempts/${attemptId}/results`);
    } catch (err) {
      console.error('Quiz submission failed:', err);
      alert('Submission error: ' + (err.response?.data?.error?.message || err.message));
    } finally {
      setSubmitting(false);
    }
  };

  const formatTime = (secs) => {
    const m = Math.floor(secs / 60);
    const s = secs % 60;
    return `${m.toString().padStart(2, '0')}:${s.toString().padStart(2, '0')}`;
  };

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary-600 border-t-transparent" />
      </div>
    );
  }

  const answeredCount = Object.keys(answers).length;
  const progressPercent = Math.round(((currentIndex + 1) / (questions.length || 1)) * 100);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      {/* Quiz Top Bar with Title & Countdown Timer */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-4 sm:px-6 shadow-sm">
        <div>
          <h1 className="text-lg font-bold text-slate-900 dark:text-white">
            {quiz?.title || 'Interactive Quiz'}
          </h1>
          <p className="text-xs text-slate-400">
            {questions.length} questions • Server evaluated on submission
          </p>
        </div>

        {/* Countdown Timer Chip */}
        <div className="flex items-center gap-2 self-start sm:self-center rounded-xl bg-amber-50 dark:bg-amber-950/40 border border-amber-200 dark:border-amber-900 px-3 py-1.5 text-amber-700 dark:text-amber-300 font-mono text-sm font-bold">
          <Clock className="h-4 w-4" />
          <span>{formatTime(timeLeft)}</span>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Main Question Card (3 columns) */}
        <div className="lg:col-span-3 rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 md:p-8 shadow-sm flex flex-col justify-between min-h-[460px]">
          <div>
            {/* Question Progress Header */}
            <div className="flex items-center justify-between text-xs text-slate-500 dark:text-slate-400 mb-2">
              <span className="font-bold text-primary-600 dark:text-primary-400">
                Question {currentIndex + 1} of {questions.length}
              </span>
              <span>{Math.round((answeredCount / (questions.length || 1)) * 100)}% Answered</span>
            </div>

            {/* Linear Progress Bar */}
            <div className="w-full bg-slate-100 dark:bg-slate-800 h-2 rounded-full overflow-hidden mb-6">
              <div
                className="bg-primary-600 h-2 rounded-full transition-all duration-300"
                style={{ width: `${progressPercent}%` }}
              />
            </div>

            {/* Question Text */}
            <h2 className="text-base md:text-lg font-bold text-slate-900 dark:text-white leading-relaxed mb-6">
              {currentQ?.question}
            </h2>

            {/* Options List */}
            <div className="space-y-3">
              {(currentQ?.options || ['True', 'False']).map((opt, i) => {
                const isSelected = answers[currentQ.id] === opt;
                return (
                  <button
                    key={i}
                    onClick={() => handleSelectOption(opt)}
                    className={`w-full flex items-center gap-3 rounded-xl p-3.5 text-sm font-medium text-left border transition-all ${
                      isSelected
                        ? 'border-primary-600 bg-primary-50/70 text-primary-900 dark:bg-primary-950/50 dark:text-primary-200 ring-1 ring-primary-600'
                        : 'border-slate-200 dark:border-surface-darkBorder bg-slate-50/40 dark:bg-slate-900/40 text-slate-800 dark:text-slate-200 hover:border-slate-300 dark:hover:border-slate-700'
                    }`}
                  >
                    <div
                      className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border text-xs font-bold transition-all ${
                        isSelected
                          ? 'border-primary-600 bg-primary-600 text-white'
                          : 'border-slate-300 dark:border-slate-600 text-slate-400'
                      }`}
                    >
                      {String.fromCharCode(65 + i)}
                    </div>
                    <span>{opt}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Action Footer */}
          <div className="flex flex-wrap items-center justify-between gap-4 pt-8 mt-6 border-t border-slate-100 dark:border-surface-darkBorder">
            <label className="flex items-center gap-2 cursor-pointer text-xs font-semibold text-slate-600 dark:text-slate-400">
              <input
                type="checkbox"
                checked={markedForReview.has(currentQ?.id)}
                onChange={toggleMarkForReview}
                className="h-4 w-4 rounded border-slate-300 text-amber-500 focus:ring-amber-400"
              />
              <Bookmark className="h-4 w-4 text-amber-500" />
              <span>Mark for Review</span>
            </label>

            <div className="flex items-center gap-2">
              <button
                disabled={currentIndex === 0}
                onClick={() => setCurrentIndex((idx) => Math.max(idx - 1, 0))}
                className="inline-flex items-center gap-1 rounded-xl border border-slate-200 dark:border-surface-darkBorder px-3.5 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-100 disabled:opacity-40"
              >
                <ChevronLeft className="h-4 w-4" />
                Previous
              </button>

              {currentIndex < questions.length - 1 ? (
                <button
                  onClick={() => setCurrentIndex((idx) => Math.min(idx + 1, questions.length - 1))}
                  className="inline-flex items-center gap-1 rounded-xl bg-primary-600 px-4 py-2 text-xs font-semibold text-white hover:bg-primary-700 shadow-sm"
                >
                  Next
                  <ChevronRight className="h-4 w-4" />
                </button>
              ) : (
                <button
                  onClick={handleSubmitQuiz}
                  disabled={submitting}
                  className="inline-flex items-center gap-1 rounded-xl bg-emerald-600 px-5 py-2 text-xs font-bold text-white hover:bg-emerald-700 shadow-sm transition-colors"
                >
                  <CheckCircle2 className="h-4 w-4" />
                  Submit Quiz
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Right Authoritative Question Navigator Grid */}
        <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-5 shadow-sm space-y-4">
          <h3 className="font-bold text-sm text-slate-900 dark:text-white">
            Question Navigator
          </h3>

          {/* Grid buttons */}
          <div className="grid grid-cols-5 gap-2">
            {questions.map((q, idx) => {
              const isCurrent = idx === currentIndex;
              const isAnswered = !!answers[q.id];
              const isMarked = markedForReview.has(q.id);

              let style = 'bg-slate-100 text-slate-600 dark:bg-slate-800 dark:text-slate-300';
              if (isMarked) {
                style = 'bg-amber-100 text-amber-800 dark:bg-amber-950/60 dark:text-amber-300 border border-amber-300';
              } else if (isAnswered) {
                style = 'bg-primary-600 text-white';
              }

              if (isCurrent) {
                style += ' ring-2 ring-primary-500 ring-offset-2 dark:ring-offset-surface-darkCard font-extrabold';
              }

              return (
                <button
                  key={idx}
                  onClick={() => setCurrentIndex(idx)}
                  className={`h-9 rounded-lg text-xs font-bold transition-all ${style}`}
                >
                  {idx + 1}
                </button>
              );
            })}
          </div>

          {/* Navigator Legend */}
          <div className="pt-4 border-t border-slate-100 dark:border-surface-darkBorder space-y-2 text-[11px] text-slate-500 dark:text-slate-400">
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded bg-primary-600" />
              <span>Answered</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded border-2 border-primary-500 bg-white" />
              <span>Current</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded bg-amber-100 border border-amber-300" />
              <span>Marked for Review</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="h-3 w-3 rounded bg-slate-100 dark:bg-slate-800" />
              <span>Not Answered</span>
            </div>
          </div>

          <button
            onClick={handleSubmitQuiz}
            disabled={submitting}
            className="w-full mt-4 rounded-xl bg-emerald-600 py-2.5 text-xs font-bold text-white hover:bg-emerald-700 shadow-sm transition-colors"
          >
            Submit Quiz
          </button>
        </div>
      </div>
    </div>
  );
};
