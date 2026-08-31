import React, { useState, useEffect, useRef } from 'react';
import { auth, db, provider } from './firebase';
import { signInWithPopup, onAuthStateChanged, signOut } from 'firebase/auth';
import { collection, addDoc, onSnapshot, query, serverTimestamp, deleteDoc, doc } from 'firebase/firestore';
import './App.css';

const API_BASE = "https://personal-book-collection-backend.onrender.com";

export default function App() {
  const [user, setUser] = useState(null);
  const [myBooks, setMyBooks] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [scanResult, setScanResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('theme') === 'dark');

  // Scanner Modes: 'cover', 'isbn', 'manual'
  const [scannerMode, setScannerMode] = useState('cover');
  const [manualIsbn, setManualIsbn] = useState('');
  
  // Manual Input form fields
  const [manualTitle, setManualTitle] = useState('');
  const [manualAuthor, setManualAuthor] = useState('');

  // UI State for tracking which book is currently prompting a delete confirmation
  const [deletingId, setDeletingId] = useState(null);

  // Camera stream states for Cover AI scan
  const [isCameraOpen, setIsCameraOpen] = useState(false);
  const videoRef = useRef(null);
  const canvasRef = useRef(null);

  useEffect(() => {
    if (darkMode) {
      document.body.classList.add('dark-mode');
      localStorage.setItem('theme', 'dark');
    } else {
      document.body.classList.remove('dark-mode');
      localStorage.setItem('theme', 'light');
    }
  }, [darkMode]);

  useEffect(() => {
    const unsubscribe = onAuthStateChanged(auth, (currentUser) => {
      setUser(currentUser);
    });
    return () => unsubscribe();
  }, []);

  useEffect(() => {
    if (!user) return;
    const q = query(collection(db, "users", user.uid, "books"));
    const unsubscribe = onSnapshot(q, (snapshot) => {
      const booksData = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
      setMyBooks(booksData);
    }, (error) => {
      console.error("Firestore Error:", error);
    });
    return () => unsubscribe();
  }, [user]);

  // ISBN Text Lookup
  const lookupIsbn = async (isbn) => {
    if (!isbn.trim()) return;
    setLoading(true);
    setScanResult(null);
    try {
      const res = await fetch(`${API_BASE}/lookup-isbn/${isbn.trim()}`);
      const data = await res.json();
      
      if (!res.ok) {
        alert(data.detail?.message || data.detail || "Book not found for this ISBN.");
        setLoading(false);
        return;
      }

      checkStockAndSetResult(data);
    } catch (err) {
      console.error("ISBN lookup error:", err);
      alert("Error connecting to book database.");
    } finally {
      setLoading(false);
    }
  };

  // Start live webcam stream for cover photo
  const startCamera = async () => {
    setIsCameraOpen(true);
    setScanResult(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
    } catch (err) {
      console.error("Camera access error:", err);
      alert("Could not access device camera. Please check permissions.");
      setIsCameraOpen(false);
    }
  };

  // Stop live webcam stream
  const stopCamera = () => {
    if (videoRef.current && videoRef.current.srcObject) {
      const tracks = videoRef.current.srcObject.getTracks();
      tracks.forEach(track => track.stop());
    }
    setIsCameraOpen(false);
  };

  // Capture image from video stream for Gemini AI scan
  const capturePhoto = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;
    if (!video || !canvas) return;

    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    canvas.toBlob((blob) => {
      const file = new File([blob], "captured-book.jpg", { type: "image/jpeg" });
      stopCamera();
      processImageScan(file);
    }, 'image/jpeg');
  };

  // Gemini AI image processing function (Cover Scan)
  const processImageScan = async (fileToScan) => {
    if (!fileToScan) return;
    setLoading(true);
    setScanResult(null);

    const formData = new FormData();
    formData.append('file', fileToScan);

    try {
      const res = await fetch(`${API_BASE}/extract-text/`, { method: 'POST', body: formData });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail);
      checkStockAndSetResult(data);
    } catch (err) {
      alert("Error scanning cover image via backend server.");
    } finally {
      setLoading(false);
    }
  };

  // Handle Manual Book Submission
  const handleManualSubmit = (e) => {
    e.preventDefault();
    if (!manualTitle.trim() || !manualAuthor.trim()) return;

    const data = {
      title: manualTitle.trim(),
      author: manualAuthor.trim(),
      isbn: manualIsbn.trim() || "N/A",
      source: "Manual Entry"
    };
    checkStockAndSetResult(data);
  };

  const checkStockAndSetResult = (data) => {
    const alreadyInStock = myBooks.some(
      book => book.title.toLowerCase().includes(data.title.toLowerCase())
    );

    setScanResult({
      ...data,
      already_in_stock: alreadyInStock,
      message: alreadyInStock 
        ? "⚠️ You already have this book at home! Please check before buying." 
        : "✅ You do not have this book in your stock. You can buy it!"
    });
  };

  const handleAddStock = async () => {
    if (!scanResult || !user) return;

    try {
      const booksRef = collection(db, "users", user.uid, "books");
      await addDoc(booksRef, {
        title: scanResult.title,
        author: scanResult.author,
        addedAt: serverTimestamp()
      });
      alert("Book successfully added to stock!");
      setScanResult(null);
      setSelectedFile(null);
      setManualIsbn('');
      setManualTitle('');
      setManualAuthor('');
    } catch (err) {
      console.error("Firebase Add Error:", err);
      alert("Failed to save book to Firebase.");
    }
  };

  // Smooth UI Execution for Deleting Book from Firestore
  const confirmRemoveBook = async (bookId) => {
    try {
      await deleteDoc(doc(db, "users", user.uid, "books", bookId));
      setDeletingId(null);
    } catch (err) {
      console.error("Firestore Delete Error:", err);
      alert("Failed to remove book from Firebase.");
    }
  };

  if (!user) {
    return (
      <div className="container center">
        <div className="card" style={{ textAlign: 'center' }}>
          <h2>📚 Personal Book Collection</h2>
          <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem' }}>Sign in to manage your home inventory</p>
          <button onClick={() => signInWithPopup(auth, provider)}>Sign in with Google</button>
          <button 
            onClick={() => setDarkMode(!darkMode)} 
            style={{ marginTop: '1rem', backgroundColor: 'transparent', color: 'var(--text-main)', border: '1px solid var(--border-color)' }}
          >
            {darkMode ? "☀️ Light Mode" : "🌙 Dark Mode"}
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <header className="header">
        <h1>📚 Personal Book Collection</h1>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'center' }}>
          <button 
            onClick={() => setDarkMode(!darkMode)} 
            style={{ width: 'auto', backgroundColor: 'transparent', color: 'var(--text-main)', border: '1px solid var(--border-color)', padding: '0.5rem 0.75rem', fontSize: '0.875rem' }}
          >
            {darkMode ? "☀️" : "🌙"}
          </button>
          <p style={{ margin: 0, fontSize: '0.9rem' }}>Hi, <strong>{user.displayName}</strong></p>
          <button onClick={() => signOut(auth)} style={{ width: 'auto', fontSize: '0.875rem', padding: '0.5rem 0.75rem' }}>Sign Out</button>
        </div>
      </header>

      <div className="main-grid">
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '5px' }}>
            <h3 style={{ margin: 0 }}>🔍 Check Stock</h3>
            <div style={{ display: 'flex', gap: '5px' }}>
              <button 
                onClick={() => { setScannerMode('cover'); setScanResult(null); stopCamera(); }}
                style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', backgroundColor: scannerMode === 'cover' ? 'var(--primary)' : '#64748b' }}
              >
                AI Cover Scan
              </button>
              <button 
                onClick={() => { setScannerMode('isbn'); setScanResult(null); stopCamera(); }}
                style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', backgroundColor: scannerMode === 'isbn' ? 'var(--primary)' : '#64748b' }}
              >
                ISBN Search
              </button>
              <button 
                onClick={() => { setScannerMode('manual'); setScanResult(null); stopCamera(); }}
                style={{ padding: '0.3rem 0.6rem', fontSize: '0.75rem', backgroundColor: scannerMode === 'manual' ? 'var(--primary)' : '#64748b' }}
              >
                Manual Entry
              </button>
            </div>
          </div>

          {/* Mode 1: Gemini AI Cover Scan */}
          {scannerMode === 'cover' && (
            <div>
              {!isCameraOpen ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
                  <button onClick={startCamera} style={{ backgroundColor: '#0284c7' }}>
                    📸 Click Cover Photo via Camera
                  </button>
                  <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>— OR UPLOAD FILE —</div>
                  <form onSubmit={(e) => { e.preventDefault(); processImageScan(selectedFile); }}>
                    <input type="file" accept="image/*" onChange={(e) => setSelectedFile(e.target.files[0])} required />
                    <button type="submit" disabled={loading || !selectedFile}>
                      {loading ? "Analyzing Cover..." : "Check Stock from File"}
                    </button>
                  </form>
                </div>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', alignItems: 'center' }}>
                  <video ref={videoRef} autoPlay playsInline style={{ width: '100%', borderRadius: '8px', maxHeight: '300px', objectFit: 'cover' }} />
                  <canvas ref={canvasRef} style={{ display: 'none' }} />
                  <div style={{ display: 'flex', gap: '10px', width: '100%' }}>
                    <button onClick={capturePhoto} style={{ flex: 1, backgroundColor: '#10b981' }}>🎯 Snap Cover</button>
                    <button onClick={stopCamera} style={{ flex: 1, backgroundColor: '#64748b' }}>Cancel</button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Mode 2: Manual ISBN Text Lookup */}
          {scannerMode === 'isbn' && (
            <form onSubmit={(e) => { e.preventDefault(); lookupIsbn(manualIsbn); }} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0 }}>
                Enter the 10 or 13-digit ISBN number:
              </p>
              <input 
                type="text" 
                placeholder="e.g., 9780143127741" 
                value={manualIsbn}
                onChange={(e) => setManualIsbn(e.target.value)}
                style={{ padding: '0.75rem', borderRadius: '8px', border: '1px solid var(--border-color)', background: 'var(--bg-color)', color: 'var(--text-main)', width: '100%', boxSizing: 'border-box' }}
                required 
              />
              <button type="submit" disabled={loading || !manualIsbn.trim()}>
                {loading ? "Searching Database..." : "Lookup ISBN"}
              </button>
            </form>
          )}

          {/* Mode 3: Direct Manual Insert */}
          {scannerMode === 'manual' && (
            <form onSubmit={handleManualSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-muted)', margin: 0 }}>
                Fill out the book details manually:
              </p>
              <input 
                type="text" 
                placeholder="Book Title" 
                value={manualTitle}
                onChange={(e) => setManualTitle(e.target.value)}
                style={{ padding: '0.6rem', borderRadius: '8px', border: '1px solid var(--border-color)', background: 'var(--bg-color)', color: 'var(--text-main)' }}
                required 
              />
              <input 
                type="text" 
                placeholder="Author Name" 
                value={manualAuthor}
                onChange={(e) => setManualAuthor(e.target.value)}
                style={{ padding: '0.6rem', borderRadius: '8px', border: '1px solid var(--border-color)', background: 'var(--bg-color)', color: 'var(--text-main)' }}
                required 
              />
              <input 
                type="text" 
                placeholder="ISBN (Optional)" 
                value={manualIsbn}
                onChange={(e) => setManualIsbn(e.target.value)}
                style={{ padding: '0.6rem', borderRadius: '8px', border: '1px solid var(--border-color)', background: 'var(--bg-color)', color: 'var(--text-main)' }}
              />
              <button type="submit">Verify & Add Manually</button>
            </form>
          )}

          {scanResult && (
            <div className={`result-box ${scanResult.already_in_stock ? 'in-stock' : 'not-in-stock'}`} style={{ marginTop: '1rem' }}>
              <p className="status-message">{scanResult.message}</p>
              <p><strong>Title:</strong> {scanResult.title}</p>
              <p><strong>Author:</strong> {scanResult.author}</p>
              {scanResult.isbn && <p><strong>ISBN:</strong> {scanResult.isbn}</p>}

              {!scanResult.already_in_stock && (
                <button onClick={handleAddStock} className="btn-add">
                  Add to My Home Stock
                </button>
              )}
            </div>
          )}
        </div>

        {/* My Library Display Card with Inline Confirmation UI */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <h3>🏠 My Home Library ({myBooks.length})</h3>
          {myBooks.length === 0 ? (
            <p style={{ color: 'var(--text-muted)' }}>No books in stock yet. Use AI Cover Scan, ISBN Search, or Manual Entry above!</p>
          ) : (
            <ul className="book-list">
              {myBooks.map((b) => (
                <li key={b.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '10px', position: 'relative', overflow: 'hidden' }}>
                  {deletingId === b.id ? (
                    // Inline confirmation view
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%', background: 'rgba(239, 68, 68, 0.1)', padding: '4px 8px', borderRadius: '6px' }}>
                      <span style={{ fontSize: '0.85rem', color: '#ef4444', fontWeight: '500' }}>Remove this book?</span>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        <button 
                          onClick={() => confirmRemoveBook(b.id)}
                          style={{ width: 'auto', backgroundColor: '#ef4444', color: '#fff', border: 'none', padding: '0.2rem 0.5rem', fontSize: '0.75rem', borderRadius: '4px', cursor: 'pointer' }}
                        >
                          Yes
                        </button>
                        <button 
                          onClick={() => setDeletingId(null)}
                          style={{ width: 'auto', backgroundColor: '#64748b', color: '#fff', border: 'none', padding: '0.2rem 0.5rem', fontSize: '0.75rem', borderRadius: '4px', cursor: 'pointer' }}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    // Standard view
                    <>
                      <div style={{ flex: 1 }}>
                        <strong>{b.title}</strong>
                        <span style={{ marginLeft: '6px', color: 'var(--text-muted)' }}>by {b.author}</span>
                      </div>
                      <button 
                        onClick={() => setDeletingId(b.id)} 
                        title="Remove book"
                        style={{ 
                          width: 'auto', 
                          background: 'transparent', 
                          color: '#ef4444', 
                          border: '1px solid #ef4444', 
                          padding: '0.25rem 0.5rem', 
                          fontSize: '0.75rem', 
                          borderRadius: '6px',
                          cursor: 'pointer',
                          transition: 'all 0.2s ease'
                        }}
                      >
                        🗑️ Remove
                      </button>
                    </>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}