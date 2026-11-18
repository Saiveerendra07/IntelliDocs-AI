import React from 'react';
import { render, screen, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { describe, it, expect } from 'vitest';
import { Login } from '../pages/Login';
import { AuthProvider } from '../context/AuthContext';

describe('Login Component', () => {
  it('renders login form with authoritative elements', () => {
    render(
      <AuthProvider>
        <BrowserRouter>
          <Login />
        </BrowserRouter>
      </AuthProvider>
    );

    expect(screen.getByText(/Welcome Back/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/student@example.com/i)).toBeInTheDocument();
    expect(screen.getByText(/Summarize Documents/i)).toBeInTheDocument();
    expect(screen.getByText(/Ask Questions \(RAG\)/i)).toBeInTheDocument();
    expect(screen.getByText(/Generate Exam Questions/i)).toBeInTheDocument();
  });

  it('validates empty email and password submission via form submit', async () => {
    const { container } = render(
      <AuthProvider>
        <BrowserRouter>
          <Login />
        </BrowserRouter>
      </AuthProvider>
    );

    const form = container.querySelector('form');
    fireEvent.submit(form);

    expect(await screen.findByText(/Please provide both email and password/i)).toBeInTheDocument();
  });
});
