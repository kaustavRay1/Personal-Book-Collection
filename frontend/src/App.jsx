import React, { useState, useEffect, useRef } from 'react';
import { auth, db, provider } from './firebase';
import { signInWithPopup, onAuthStateChanged, signOut } from 'firebase/auth';
import { collection, addDoc, onSnapshot, query, serverTimestamp } from 'firebase/firestore';
import './App.css';

const API_BASE = "https://personal-book-collection-backend.onrender.com";

export default function App() {
  const [user, setUser] = useState(null);
  const [myBooks, setMyBooks] = useState([]);
  const [selectedFile, setSelectedFile] = useState(null);
  const [scanResult, setScanResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [darkMode, setDarkMode] = useState(() => localStorage.getItem('theme') === 'dark');

  // Camera stream states
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
      console.error("Firestore Permission or Fetch Error:", error);
    });
    return () => unsubscribe();
  }, [user]);

  // Start live webcam stream
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
      alert("Could not access device camera. Please check permissions or use file upload.");
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

  // Capture image from video stream
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
      setSelectedFile(file);
      stopCamera();
      // Automatically trigger scan with the captured photo
      processImageScan(file);
    }, 'image/jpeg');
  };

  const handleLogin = async () => {
    try {
      await signInWithPopup(auth, provider);
    } catch (error) {
      alert("Error signing in with Google");
    }
  };

  const processImageScan = async (fileToScan) => {
    if (!fileToScan) return;

    setLoading(true);
    setScanResult(null);

    const formData = new FormData();
    formData.append('file', fileToScan);

    try {
      const res = await fetch(`${API_BASE}/extract-text/`, { method: 'POST', body: formData });
      const data = await res.json();
      
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
    } catch (err) {
      alert("Error scanning image via backend server.");
    } finally {
      setLoading(false);
    }
  };

  const handleScanSubmit = (e) => {
    e.preventDefault();
    processImageScan(selectedFile);
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
    } catch (err) {
      console.error("Firebase Add Error:", err);
      alert("Failed to save book to Firebase. Check Firestore Rules.");
    }
  };

  if (!user) {
    return (
      <div className="container center">
        <div className="card" style={{ textAlign: 'center' }}>
          <h2>📚 Personal Book Collection</h2>
          <p style={{ color: 'var(--text-muted)', marginBottom: '1.5rem' }}>Sign in to manage your home inventory</p>
          <button onClick={handleLogin}>Sign in with Google</button>
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
        {/* Scan Card */}
        <div className="card">
          <h3>📷 Scan Front Cover</h3>

          {!isCameraOpen ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <button onClick={startCamera} style={{ backgroundColor: '#0284c7' }}>
                📸 Click Photo via Camera
              </button>

              <div style={{ textAlign: 'center', color: 'var(--text-muted)', fontSize: '0.85rem' }}>— OR UPLOAD FILE —</div>

              <form onSubmit={handleScanSubmit}>
                <input 
                  type="file" 
                  accept="image/*" 
                  onChange={(e) => setSelectedFile(e.target.files[0])} 
                  required 
                />
                <button type="submit" disabled={loading || !selectedFile}>
                  {loading ? "Analyzing with AI..." : "Check Stock from File"}
                </button>
              </form>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem', alignItems: 'center' }}>
              <video ref={videoRef} autoPlay playsInline style={{ width: '100%', borderRadius: '8px', maxHeight: '300px', objectFit: 'cover' }} />
              <canvas ref={canvasRef} style={{ display: 'none' }} />
              
              <div style={{ display: 'flex', gap: '10px', width: '100%' }}>
                <button onClick={capturePhoto} style={{ flex: 1, backgroundColor: '#10b981' }}>
                  🎯 Snap & Scan
                </button>
                <button onClick={stopCamera} style={{ flex: 1, backgroundColor: '#64748b' }}>
                  Cancel
                </button>
              </div>
            </div>
          )}

          {scanResult && (
            <div className={`result-box ${scanResult.already_in_stock ? 'in-stock' : 'not-in-stock'}`}>
              <p className="status-message">{scanResult.message}</p>
              <p><strong>Detected Title:</strong> {scanResult.title}</p>
              <p><strong>Detected Author:</strong> {scanResult.author}</p>

              {!scanResult.already_in_stock && (
                <button onClick={handleAddStock} className="btn-add">
                  Add to My Home Stock
                </button>
              )}
            </div>
          )}
        </div>

        {/* My Library Display Card */}
        <div className="card" style={{ gridColumn: '1 / -1' }}>
          <h3>🏠 My Home Library ({myBooks.length})</h3>
          {myBooks.length === 0 ? (
            <p style={{ color: 'var(--text-muted)' }}>No books in stock yet. Scan a book cover above!</p>
          ) : (
            <ul className="book-list">
              {myBooks.map((b) => (
                <li key={b.id}>
                  <strong>{b.title}</strong>
                  <span>by {b.author}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
}