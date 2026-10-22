import React from 'react'
import ReactDOM from 'react-dom/client'
import './styles.css'

function App() {
  return (
    <main>
      <p className="eyebrow">SUPPORTOPS AI · DEVELOPMENT SCAFFOLD</p>
      <h1>Make every support action traceable.</h1>
      <p>A ticket and knowledge collaboration platform for a fictional software support team.</p>
      <section aria-labelledby="status-heading">
        <h2 id="status-heading">Current stage: application foundation</h2>
        <p>The API foundation and frontend scaffold are in place. Business pages, knowledge retrieval, and AI review follow the milestone plan.</p>
        <ol>
          <li>Define role permissions, business states, and API contracts</li>
          <li>Build the database, authentication, and ticket workflow</li>
          <li>Add knowledge retrieval, cited drafts, and human review</li>
        </ol>
      </section>
    </main>
  )
}

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><App /></React.StrictMode>,
)
