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
  const [editingId, setEditingId] = useState(null)

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

  const submitFeature = async () => {
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

      const payload = {
        feature_type: selectedType,
        name: featureName,
        geometry_data: geometry,
        properties: {},
        source: 'admin',
      }

      const result = editingId
        ? await updateFeature(editingId, payload)
        : await createFeature(payload)

      if (result.success) {
        setMessage({
          type: 'success',
          text: editingId ? 'Feature updated successfully' : 'Feature created successfully',
        })
        setFeatureName('')
        setCoordinates('')
        setEditingId(null)
        await loadFeatures()
      } else {
        setMessage({ type: 'error', text: result.error?.message || 'Failed to save feature' })
      }
    } catch (err) {
      setMessage({ type: 'error', text: err.message })
    } finally {
      setLoading(false)
    }
  }

  const handleCreate = async () => {
    await submitFeature()
  }

  const handleEdit = (feature) => {
    setEditingId(feature.id)
    setSelectedType(feature.feature_type)
    setFeatureName(feature.name || '')
    setCoordinates(JSON.stringify(feature.geometry_data?.coordinates || [], null, 2))
    setMessage({ type: 'info', text: `Editing ${feature.name || feature.feature_type}` })
  }

  const handleDelete = async (id) => {
    if (!confirm('Are you sure you want to delete this feature?')) return

    try {
      setLoading(true)
      const result = await deleteFeature(id)
      if (result.success) {
        setMessage({ type: 'success', text: 'Feature deleted' })
        if (editingId === id) {
          setEditingId(null)
          setFeatureName('')
          setCoordinates('')
        }
        await loadFeatures()
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
          <div className="button-row" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap' }}>
            <button className="btn btn-primary" onClick={handleCreate} disabled={loading}>
              {loading ? (editingId ? 'Saving...' : 'Creating...') : (editingId ? 'Save Changes' : 'Create Feature')}
            </button>
            {editingId && (
              <button
                className="btn btn-secondary"
                onClick={() => {
                  setEditingId(null)
                  setFeatureName('')
                  setCoordinates('')
                  setMessage(null)
                }}
              >
                Cancel
              </button>
            )}
          </div>
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
                <div className="feature-actions" style={{ display: 'flex', gap: '0.5rem' }}>
                  <button className="btn btn-secondary btn-sm" onClick={() => handleEdit(f)}>
                    Edit
                  </button>
                  <button className="btn btn-danger btn-sm" onClick={() => handleDelete(f.id)}>
                    Delete
                  </button>
                </div>
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
