/**
 * Search box component for finding campus places.
 */
import React, { useState, useCallback, useRef, useEffect } from 'react'

export default function SearchBox({ places = [], onPlaceSelect, selectedPlace }) {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [isOpen, setIsOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const inputRef = useRef(null)
  const debounceRef = useRef(null)

  // Debounced search
  const handleSearch = useCallback((value) => {
    if (debounceRef.current) {
      clearTimeout(debounceRef.current)
    }

    if (!value.trim()) {
      setResults([])
      setIsOpen(false)
      return
    }

    debounceRef.current = setTimeout(() => {
      setLoading(true)
      const searchLower = value.toLowerCase()
      const filtered = places
        .filter(p => p.name.toLowerCase().includes(searchLower))
        .slice(0, 10)
      setResults(filtered)
      setIsOpen(true)
      setLoading(false)
    }, 200)
  }, [places])

  useEffect(() => {
    handleSearch(query)
  }, [query, handleSearch])

  // Close on outside click
  useEffect(() => {
    const handleClickOutside = (e) => {
      if (inputRef.current && !inputRef.current.contains(e.target)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const handleSelect = (place) => {
    onPlaceSelect?.(place)
    setQuery(place.name)
    setIsOpen(false)
  }

  const handleClear = () => {
    setQuery('')
    setResults([])
    setIsOpen(false)
    onPlaceSelect?.(null)
  }

  return (
    <div className="search-box" ref={inputRef}>
      <div className="search-input-wrapper">
        <svg className="search-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="11" cy="11" r="8" />
          <path d="m21 21-4.35-4.35" />
        </svg>
        <input
          type="text"
          placeholder="Search campus places..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onFocus={() => query && setIsOpen(true)}
          className="search-input"
        />
        {query && (
          <button className="search-clear" onClick={handleClear}>
            ×
          </button>
        )}
      </div>

      {isOpen && results.length > 0 && (
        <div className="search-results">
          {results.map(place => (
            <button
              key={place.id}
              className="search-result-item"
              onClick={() => handleSelect(place)}
            >
              <div className="result-name">{place.name}</div>
              <div className="result-category">{place.category}</div>
            </button>
          ))}
        </div>
      )}

      {isOpen && query && results.length === 0 && !loading && (
        <div className="search-results">
          <div className="no-results">No places found</div>
        </div>
      )}
    </div>
  )
}
