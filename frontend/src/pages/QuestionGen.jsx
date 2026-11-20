import React, { useEffect, useState } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  HelpCircle,
  Sparkles,
  Award,
  CheckCircle2,
  FileText,
  Sliders,
  Plus,
} from 'lucide-react';
import { documentsApi } from '../api/documents';
import { quizApi } from '../api/quiz';
import { Badge } from '../components/common/Badge';

export const QuestionGen = () => {
  const [searchParams] = useSearchParams();
  const initialDocId = searchParams.get('documentId') || '';
  const initialTopic = searchParams.get('topic') || '';

  const [documents, setDocuments] = useState([]);
  const [selectedDocId, setSelectedDocId] = useState(initialDocId);
  const [questionType, setQuestionType] = useState('mcq'); // mcq, true_false, fill_blank, short_answer, long_answer, conceptual, application
  const [difficulty, setDifficulty] = useState('medium'); // easy, medium, hard
  const [count, setCount] = useState(5);
  const [topic, setTopic] = useState(initialTopic);

  const [generatedQuestions, setGeneratedQuestions] = useState([]);
  const [showAnswers, setShowAnswers] = useState(false);
  const [loading, setLoading] = useState(false);
  const [savingQuiz, setSavingQuiz] = useState(false);
  const [savedQuizId, setSavedQuizId] = useState(null);

  const navigate = useNavigate();

  useEffect(() => {
    const fetchDocs = async () => {
      try {
        const res = await documentsApi.list();
        const items = res.items || [];
        setDocuments(items);
        if (!selectedDocId && items.length > 0) {
          setSelectedDocId(items[0].id);
        }
      } catch (e) {
        console.error(e);
      }
    };
    fetchDocs();
  }, []);

  const handleGenerate = async () => {
    if (!selectedDocId) return;
    setLoading(true);
    setSavedQuizId(null);
    try {
      const res = await quizApi.generateQuestions({
        document_id: selectedDocId,
        type: questionType,
        difficulty,
        count: parseInt(count, 10),
        topic: topic || undefined,
      });
      setGeneratedQuestions(res.questions || res || []);
    } catch (err) {
      console.error('Question generation failed:', err);
      alert('Generation error: ' + (err.response?.data?.error?.message || err.message));
    } finally {
      setLoading(false);
    }
  };

  const createQuizRecord = async () => {
    const selectedDoc = documents.find((d) => d.id === selectedDocId);
    const title = `${selectedDoc?.original_filename || 'Document'} Quiz - ${new Date().toLocaleDateString()}`;
    return await quizApi.createQuiz({
      document_id: selectedDocId,
      title,
      question_ids: generatedQuestions.map((q) => q.id),
      time_limit_seconds: generatedQuestions.length * 60, // 1 min per question
    });
  };

  const handleStartQuiz = async () => {
    if (generatedQuestions.length === 0) return;
    setSavingQuiz(true);
    try {
      const quiz = await createQuizRecord();
      navigate(`/quizzes/${quiz.id}`);
    } catch (err) {
      console.error('Start quiz failed:', err);
      alert('Failed to start quiz: ' + err.message);
    } finally {
      setSavingQuiz(false);
    }
  };

  const handleSaveAsQuiz = async () => {
    if (generatedQuestions.length === 0) return;
    setSavingQuiz(true);
    try {
      const quiz = await createQuizRecord();
      setSavedQuizId(quiz.id);
    } catch (err) {
      console.error('Save quiz failed:', err);
      alert('Failed to save quiz: ' + err.message);
    } finally {
      setSavingQuiz(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">
            Automatic Question Generation
          </h1>
          <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
            Synthesize genuine exam questions from document key sentences, definitions, and semantic embeddings.
          </p>
        </div>

        {generatedQuestions.length > 0 && (
          <div className="flex items-center gap-2">
            <button
              onClick={handleSaveAsQuiz}
              disabled={savingQuiz}
              className="inline-flex items-center gap-1.5 rounded-xl border border-slate-300 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard px-3.5 py-2 text-xs font-semibold text-slate-700 dark:text-slate-200 hover:bg-slate-50 transition-colors shadow-sm"
            >
              <Award className="h-4 w-4 text-primary-600" />
              <span>{savedQuizId ? 'Saved ✓' : 'Save as Quiz'}</span>
            </button>
            <button
              onClick={handleStartQuiz}
              disabled={savingQuiz}
              className="inline-flex items-center gap-1.5 rounded-xl bg-emerald-600 px-4 py-2 text-xs font-semibold text-white shadow-sm hover:bg-emerald-700 transition-colors"
            >
              <Sparkles className="h-4 w-4" />
              <span>Start Quiz</span>
            </button>
          </div>
        )}
      </div>

      {savedQuizId && (
        <div className="rounded-xl border border-emerald-200 bg-emerald-50/80 dark:border-emerald-900/50 dark:bg-emerald-950/30 p-3.5 text-xs text-emerald-900 dark:text-emerald-200 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-600" />
            <span>Quiz created successfully! Ready to take anytime.</span>
          </div>
          <button
            onClick={() => navigate(`/quizzes/${savedQuizId}`)}
            className="font-bold underline hover:text-emerald-700"
          >
            Launch Quiz Now →
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Left Column: Authoritative Config Card */}
        <div className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm space-y-5 h-fit">
          <h2 className="text-base font-bold text-slate-900 dark:text-white flex items-center gap-2">
            <Sliders className="h-4 w-4 text-primary-600" />
            Generation Parameters
          </h2>

          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
              Source Document
            </label>
            <select
              value={selectedDocId}
              onChange={(e) => setSelectedDocId(e.target.value)}
              className="w-full rounded-xl border border-slate-300 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard px-3 py-2 text-sm text-slate-800 dark:text-white focus:border-primary-600 focus:outline-none"
            >
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.original_filename}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
              Question Format
            </label>
            <select
              value={questionType}
              onChange={(e) => setQuestionType(e.target.value)}
              className="w-full rounded-xl border border-slate-300 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard px-3 py-2 text-sm text-slate-800 dark:text-white focus:border-primary-600 focus:outline-none"
            >
              <option value="mcq">Multiple Choice (MCQ)</option>
              <option value="true_false">True / False</option>
              <option value="fill_blank">Fill in the Blank</option>
              <option value="short_answer">Short Answer</option>
              <option value="long_answer">Long Answer</option>
              <option value="conceptual">Conceptual Reasoning</option>
              <option value="application">Application-Based</option>
            </select>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
              Difficulty Tier
            </label>
            <div className="grid grid-cols-3 gap-2">
              {['easy', 'medium', 'hard'].map((d) => (
                <button
                  key={d}
                  onClick={() => setDifficulty(d)}
                  className={`rounded-xl py-2 text-xs font-bold capitalize transition-all border ${
                    difficulty === d
                      ? 'border-primary-600 bg-primary-50 text-primary-700 dark:bg-primary-950/60 dark:text-primary-300 shadow-xs'
                      : 'border-slate-200 dark:border-surface-darkBorder text-slate-600 dark:text-slate-400 hover:bg-slate-50'
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider">
                Number of Questions
              </label>
              <span className="text-xs font-bold text-primary-600">{count}</span>
            </div>
            <input
              type="range"
              min="1"
              max="15"
              value={count}
              onChange={(e) => setCount(e.target.value)}
              className="w-full accent-primary-600"
            />
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-500 uppercase tracking-wider mb-1.5">
              Target Topic (Optional)
            </label>
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              placeholder="e.g. Virtual Memory"
              className="w-full rounded-xl border border-slate-300 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard px-3 py-2 text-xs text-slate-800 dark:text-white placeholder:text-slate-400 focus:outline-none"
            />
          </div>

          <button
            onClick={handleGenerate}
            disabled={loading || !selectedDocId}
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-primary-600 py-3 text-sm font-semibold text-white shadow-md shadow-primary-700/20 hover:bg-primary-700 disabled:opacity-50 transition-all"
          >
            {loading ? (
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
            ) : (
              <Sparkles className="h-4 w-4" />
            )}
            <span>Generate Questions</span>
          </button>
        </div>

        {/* Right Column: Generated Questions Cards */}
        <div className="lg:col-span-2 space-y-4">
          {generatedQuestions.length > 0 && (
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-3.5 shadow-sm text-xs">
              <span className="font-semibold text-slate-700 dark:text-slate-300">
                Previewing {generatedQuestions.length} generated items
              </span>
              <label className="flex items-center gap-2 cursor-pointer font-semibold text-slate-600 dark:text-slate-400 select-none">
                <input
                  type="checkbox"
                  checked={showAnswers}
                  onChange={(e) => setShowAnswers(e.target.checked)}
                  className="h-4 w-4 rounded border-slate-300 text-primary-600 focus:ring-primary-500"
                />
                <span>Show answers (Teacher review)</span>
              </label>
            </div>
          )}

          {generatedQuestions.length > 0 && generatedQuestions[0]?.provider_notice && (
            <div className="rounded-xl border border-blue-200 bg-blue-50/70 dark:border-blue-900/40 dark:bg-blue-950/30 p-3 text-xs text-blue-800 dark:text-blue-300 flex items-center gap-2">
              <Sparkles className="h-4 w-4 shrink-0 text-blue-600" />
              <span>{generatedQuestions[0].provider_notice}</span>
            </div>
          )}

          {generatedQuestions.length === 0 ? (
            <div className="flex flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-200 dark:border-surface-darkBorder p-12 text-center bg-white/40 dark:bg-surface-darkCard/20">
              <HelpCircle className="h-12 w-12 text-primary-400 mb-3" />
              <h3 className="text-base font-bold text-slate-800 dark:text-white">
                No questions generated yet
              </h3>
              <p className="text-xs text-slate-400 mt-1 max-w-sm">
                Select your document and question format on the left, then click "Generate Questions".
              </p>
            </div>
          ) : (
            generatedQuestions.map((q, idx) => (
              <div
                key={idx}
                className="rounded-xl border border-slate-200/80 dark:border-surface-darkBorder bg-white dark:bg-surface-darkCard p-6 shadow-sm space-y-3"
              >
                <div className="flex items-center justify-between text-xs">
                  <div className="flex items-center gap-2">
                    <span className="font-bold text-primary-600">Question {idx + 1}</span>
                    <Badge variant="neutral">{q.type || questionType}</Badge>
                    <Badge variant={q.difficulty === 'hard' ? 'danger' : 'warning'}>
                      {q.difficulty || difficulty}
                    </Badge>
                  </div>
                  {q.page && (
                    <span className="text-slate-400 font-mono">[Page {q.page}]</span>
                  )}
                </div>

                <h3 className="font-bold text-sm text-slate-900 dark:text-white leading-relaxed">
                  {q.question}
                </h3>

                {/* Multiple Choice Options Preview */}
                {q.options && q.options.length > 0 && (q.type === 'mcq' || !q.type) && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-1">
                    {q.options.map((opt, i) => {
                      const isCorrect = showAnswers && opt === q.correct_answer;
                      return (
                        <div
                          key={i}
                          className={`rounded-lg p-2.5 text-xs font-medium border transition-colors ${
                            isCorrect
                              ? 'border-emerald-300 bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800 font-bold'
                              : 'border-slate-200 dark:border-surface-darkBorder bg-slate-50 dark:bg-slate-900/40 text-slate-700 dark:text-slate-300'
                          }`}
                        >
                          <span className="font-bold mr-2">{String.fromCharCode(65 + i)}.</span>
                          <span>{opt}</span>
                          {isCorrect && (
                            <span className="ml-2 text-[10px] font-bold text-emerald-600">✓ Correct</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* True/False Options Preview */}
                {(q.type === 'true_false' || q.type === 'boolean') && (
                  <div className="flex items-center gap-3 pt-1">
                    {['True', 'False'].map((tf, i) => {
                      const isCorrect = showAnswers && q.correct_answer?.toLowerCase().startsWith(tf.toLowerCase());
                      return (
                        <div
                          key={i}
                          className={`flex-1 rounded-lg p-2.5 text-xs text-center font-bold border transition-colors ${
                            isCorrect
                              ? 'border-emerald-300 bg-emerald-50 text-emerald-800 dark:bg-emerald-950/40 dark:text-emerald-300'
                              : 'border-slate-200 dark:border-surface-darkBorder bg-slate-50 dark:bg-slate-900/40 text-slate-700 dark:text-slate-300'
                          }`}
                        >
                          {tf} {isCorrect && '✓'}
                        </div>
                      );
                    })}
                  </div>
                )}

                {/* Fill-in-the-blank Preview */}
                {(q.type === 'fill_blank' || q.type === 'fill_in_blank') && (
                  <div className="pt-1">
                    {showAnswers ? (
                      <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 p-2.5 text-xs text-emerald-900 dark:text-emerald-200 font-semibold">
                        Expected Blank Value: <span className="underline font-bold">{q.correct_answer}</span>
                      </div>
                    ) : (
                      <div className="rounded-lg bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-surface-darkBorder p-2.5 text-xs text-slate-400 italic">
                        [Fill-in-the-blank text input - answer hidden]
                      </div>
                    )}
                  </div>
                )}

                {/* Short / Long Answer Preview */}
                {['short_answer', 'long_answer', 'conceptual', 'application'].includes(q.type) && (
                  <div className="pt-1">
                    {showAnswers ? (
                      <div className="rounded-lg bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 p-2.5 text-xs text-emerald-900 dark:text-emerald-200">
                        <span className="font-bold">Model Answer: </span>
                        {q.correct_answer}
                      </div>
                    ) : (
                      <div className="rounded-lg bg-slate-50 dark:bg-slate-900/40 border border-slate-200 dark:border-surface-darkBorder p-2.5 text-xs text-slate-400 italic">
                        [Text response area - model answer hidden]
                      </div>
                    )}
                  </div>
                )}

                {/* Plain-Language Explanation (Only when showAnswers is ON) */}
                {showAnswers && q.explanation && (
                  <div className="rounded-lg bg-primary-50/50 dark:bg-primary-950/20 p-3 text-xs text-slate-600 dark:text-slate-300 border-l-2 border-primary-600">
                    <span className="font-bold text-primary-700 dark:text-primary-400">
                      Explanation:{' '}
                    </span>
                    {q.explanation}
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
};
