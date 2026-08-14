import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Layout } from '@/components/Layout'

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: false } },
})

describe('Avana Redesign UI Shell', () => {
  it('renders global app shell header with AVANA branding', () => {
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Layout />
        </BrowserRouter>
      </QueryClientProvider>
    )

    expect(screen.getByText('AVANA')).toBeInTheDocument()
    expect(screen.getByText('V2')).toBeInTheDocument()
  })

  it('renders bottom navigation items including SOS tab', () => {
    render(
      <QueryClientProvider client={queryClient}>
        <BrowserRouter>
          <Layout />
        </BrowserRouter>
      </QueryClientProvider>
    )

    expect(screen.getByText('Home')).toBeInTheDocument()
    expect(screen.getByText('Map')).toBeInTheDocument()
    expect(screen.getByText('Report')).toBeInTheDocument()
    expect(screen.getByText('SOS')).toBeInTheDocument()
    expect(screen.getByText('Profile')).toBeInTheDocument()
  })
})
