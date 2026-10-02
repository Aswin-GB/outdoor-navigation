/**
 * Search box component for finding campus places.
 */
import React, { useState, useCallback, useRef, useEffect } from 'react'

export default function SearchBox({
  places = [],
  onPlaceSelect,
  selectedPlace,
  position,
  locationLoading = false,
  locationError = null,
  onLocate,
}) {
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
          <button
            type="button"
            className="search-clear"
            onClick={handleClear}
            aria-label="Clear place search"
          >
            ×
          </button>
        )}
        <button
          type="button"
          className={`location-button${position ? ' has-location' : ''}${locationLoading ? ' is-loading' : ''}`}
          onClick={onLocate}
          disabled={locationLoading}
          aria-label={locationError ? `Location unavailable: ${locationError}` : 'Find my location'}
          title={locationError || (position ? 'Update my location' : 'Find my location')}
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3" />
            <path d="M12 2v2m0 16v2M2 12h2m16 0h2" />
            <circle cx="12" cy="12" r="8" />
          </svg>
        </button>
      </div>
      <div className={`location-status${locationError ? ' has-error' : ''}`} aria-live="polite">
        {locationLoading
          ? 'Finding your location…'
          : locationError
            ? 'Location unavailable — check browser permission'
            : position
              ? `Location ready${position.accuracy ? ` · ±${Math.round(position.accuracy)} m` : ''}`
              : 'Waiting for location permission'}
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
              <div className="result-category">{place.category || 'Campus place'}</div>
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
