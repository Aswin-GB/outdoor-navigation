/**
 * Admin map editor component.
 */
import React, { useState, useCallback } from 'react'
import { createFeature, updateFeature, deleteFeature, getFeatures } from '../../services/mapApi'

const FEATURE_TYPES = [
  { value: 'road', label: 'Road' },
  { value: 'path', label: 'Path' },
  { value: 'pedestrian_area', label: 'Pedestrian Area' },
  { value: 'building', label: 'Building' },
  { value: 'gate', label: 'Gate' },
  { value: 'parking', label: 'Parking' },
  { value: 'landmark', label: 'Landmark' },
  { value: 'facility', label: 'Facility' },
  { value: 'other', label: 'Other' },
]

export default function MapEditor({ mapData }) {
  const [features, setFeatures] = useState([])
  const [selectedType, setSelectedType] = useState('road')
  const [featureName, setFeatureName] = useState('')
  const [coordinates, setCoordinates] = useState('')
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState(null)

  // Load features
  const loadFeatures = useCallback(async () => {
    try {
      const result = await getFeatures()
      if (result.success) {
        setFeatures(result.data)
      }
    } catch (err) {
      console.error('Failed to load features:', err)
    }
  }, [])

  React.useEffect(() => {
    loadFeatures()
  }, [loadFeatures])

  // Create feature
  const handleCreate = async () => {
    if (!coordinates) {
      setMessage({ type: 'error', text: 'Coordinates are required' })
      return
    }

    try {
      setLoading(true)
      const coords = JSON.parse(coordinates)
      const geometry = {
        type: selectedType === 'building' || selectedType === 'pedestrian_area' ? 'Polygon' : 'LineString',
        coordinates: coords,
      }

      const result = await createFeature({
        feature_type: selectedType,
        name: featureName,
        geometry_data: geometry,
        properties: {},
        source: 'admin',
      })

      if (result.success) {
        setMessage({ type: 'success', text: 'Feature created successfully' })
        setFeatureName('')
        setCoordinates('')
        loadFeatures()
      } else {
        setMessage({ type: 'error', text: result.error?.message || 'Failed to create feature' })
      }
    } catch (err) {
      setMessage({ type: 'error', text: err.message })
    } finally {
      setLoading(false)
    }
  }

  // Delete feature
  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this feature?')) return

    try {
      setLoading(true)
      const result = await deleteFeature(id)
      if (result.success) {
        setMessage({ type: 'success', text: 'Feature deleted' })
        loadFeatures()
      }
    } catch (err) {
      setMessage({ type: 'error', text: err.message })
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="map-editor">
      <div className="editor-header">
        <h2>Map Editor</h2>
        <p>Add, edit, or remove campus features</p>
      </div>

      {message && (
        <div className={`alert alert-${message.type}`}>
          {message.text}
        </div>
      )}

      <div className="editor-content">
        {/* Create Feature Form */}
        <div className="editor-section">
          <h3>Add Feature</h3>
          <div className="form-group">
            <label>Feature Type</label>
            <select value={selectedType} onChange={(e) => setSelectedType(e.target.value)}>
              {FEATURE_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div className="form-group">
            <label>Name</label>
            <input
              type="text"
              value={featureName}
              onChange={(e) => setFeatureName(e.target.value)}
              placeholder="Feature name"
            />
          </div>
          <div className="form-group">
            <label>Coordinates (JSON)</label>
            <textarea
              value={coordinates}
              onChange={(e) => setCoordinates(e.target.value)}
              placeholder='[[77.68, 9.57], [77.69, 9.58]]'
              rows={4}
            />
          </div>
          <button className="btn btn-primary" onClick={handleCreate} disabled={loading}>
            {loading ? 'Creating...' : 'Create Feature'}
          </button>
        </div>

        {/* Feature List */}
        <div className="editor-section">
          <h3>Existing Features</h3>
          <div className="feature-list">
            {features.map(f => (
              <div key={f.id} className="feature-item">
                <div className="feature-info">
                  <span className="feature-name">{f.name || 'Unnamed'}</span>
                  <span className="feature-type">{f.feature_type}</span>
                </div>
                <button className="btn btn-danger btn-sm" onClick={() => handleDelete(f.id)}>
                  Delete
                </button>
              </div>
            ))}
            {features.length === 0 && (
              <p className="no-features">No custom features yet</p>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}
