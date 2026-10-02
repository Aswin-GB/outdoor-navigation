/**
 * Base API service for CampusFlow.
 */
const normalizeBaseUrl = (baseUrl, fallback) => {
  const candidate = (baseUrl || fallback).trim().replace(/\/+$/, '')
  return candidate || fallback
}

const API_BASE = normalizeBaseUrl(import.meta.env.VITE_API_BASE_URL, 'http://localhost:8000')

const getUrl = (path) => {
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${API_BASE}${normalizedPath}`
}

export async function apiGet(path) {
  const response = await fetch(getUrl(path))
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.error?.message || `HTTP ${response.status}`)
  }
  return response.json()
}

export async function apiPost(path, data) {
  const response = await fetch(getUrl(path), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.error?.message || `HTTP ${response.status}`)
  }
  return response.json()
}

export async function apiPut(path, data) {
  const response = await fetch(getUrl(path), {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.error?.message || `HTTP ${response.status}`)
  }
  return response.json()
}

export async function apiDelete(path) {
  const response = await fetch(getUrl(path), {
    method: 'DELETE',
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.error?.message || `HTTP ${response.status}`)
  }
  return response.json()
}
