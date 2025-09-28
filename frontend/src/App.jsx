import React, { useState } from "react";
import axios from "axios";

export default function App() {
  const [query, setQuery] = useState("");
  const [data, setData] = useState(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState("");

  const run = async () => {
    if (!query.trim()) return;
    setBusy(true);
    setErr("");
    setData(null);
    try {
      const res = await axios.get("http://127.0.0.1:5000/search", {
        params: { q: query, max_results: 5 },
      });
      setData(res.data);
    } catch (e) {
      setErr(e?.message || "Request failed");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="wrap">
      <h1>Multi-Source Research Agent</h1>
      <div className="bar">
        <input
          placeholder="e.g., reinforcement learning 2025"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && run()}
        />
        <button onClick={run} disabled={busy}>Search</button>
      </div>

      {busy && <p>Loading…</p>}
      {err && <p className="err">{err}</p>}

      {data && (
        <>
          <section>
            <h2>Summary</h2>
            <div className="card pre">{data.summary || "—"}</div>
          </section>

          <section>
            <h2>arXiv Papers</h2>
            {data.arxiv?.length ? data.arxiv.map((p, i) => (
              <div className="card" key={i}>
                <a href={p.link} target="_blank" rel="noreferrer">{p.title}</a>
                <p>{p.summary}</p>
                <small>{p.published}</small>
              </div>
            )) : <p>—</p>}
          </section>

          <section>
            <h2>News</h2>
            {data.news?.length ? data.news.map((n, i) => (
              <div className="card" key={i}>
                <a href={n.url} target="_blank" rel="noreferrer">{n.title}</a>
                <p>{n.summary}</p>
                <small>{n.published}</small>
              </div>
            )) : <p>—</p>}
          </section>

          <section>
            <h2>Blogs</h2>
            {data.blogs?.length ? data.blogs.map((b, i) => (
              <div className="card" key={i}>
                <a href={b.link} target="_blank" rel="noreferrer">{b.title}</a>
                <p>{b.summary}</p>
                <small>{b.published}</small>
              </div>
            )) : <p>—</p>}
          </section>
        </>
      )}
    </div>
  );
}
