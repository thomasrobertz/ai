import React, { useState } from 'react';
import { marked } from 'marked';

// API base URL configuration
const API_BASE_URL = process.env.NODE_ENV === 'production' 
    ? '/edi_demo/api' 
    : 'http://localhost:5000';

function App() {
    const [query, setQuery] = useState('');
    const [response, setResponse] = useState('');
    const [formattedResponse, setFormattedResponse] = useState('');
    const [similarities, setSimilarities] = useState([]);
    const [topKSimilarity, setTopKSimilarity] = useState(null);
    const [isLoading, setIsLoading] = useState(false);
    const [showExamples, setShowExamples] = useState(true);

    const examplePrompts = [
        "Tell me about the element with code 1001.",
        "Show me all elements related to dates.",
        "Explain the usage of code 7431.",
        "What does an..7 mean?",
        "List 4 elements with numeric representation.",
        "What elements are used for identification?",
        "What is the usage description for usage [I]?",
        "Which elements use alphanumeric format?",
        "Explain the difference between n2 and n..2",
        "What are conditional elements?",
        "Which element has the description containing 'specify' and 'level'?",
        "What would be the representation for 'up to 20 numeric characters'?"
    ];

    const handlePromptClick = (prompt) => {
        setQuery(prompt);
        // Add flash animation by temporarily adding the 'clicked' class
        const elements = document.getElementsByClassName('example-prompt');
        for (let el of elements) {
            if (el.textContent === prompt) {
                el.classList.add('clicked');
                setTimeout(() => el.classList.remove('clicked'), 600); // Remove after animation
                break;
            }
        }
    };

    const handleQueryChange = (e) => {
        setQuery(e.target.value);
    };

    const handleQuerySubmit = async (e) => {
        e.preventDefault();
        setResponse(''); // Clear previous response
        setFormattedResponse(''); // Clear previous formatted response
        setSimilarities([]); // Clear previous similarities
        setTopKSimilarity(null); // Clear top-K similarity
        setIsLoading(true); // Set loading state

        try {
            // Get the RAG context
            const contextResponse = await fetch(`${API_BASE_URL}/context`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query }),
            });

            if (!contextResponse.ok) {
                throw new Error('Failed to fetch context');
            }

            const contextData = await contextResponse.json();
            if (contextData.error) {
                setResponse('Error: ' + contextData.error);
                setIsLoading(false);
                return;
            }

            // Set top-k similarity and individual similarities
            setTopKSimilarity(contextData.top_k_similarity);
            setSimilarities(contextData.similarities);

            // Start streaming the OpenAI response
            const responseStream = await fetch(`${API_BASE_URL}/query`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query }),
            });

            if (!responseStream.ok) {
                throw new Error('Network response was not ok');
            }

            const reader = responseStream.body.getReader();
            const decoder = new TextDecoder();
            let done = false;
            let tempResponse = '';

            while (!done) {
                const { value, done: streamDone } = await reader.read();
                done = streamDone;
                if (value) {
                    const chunk = decoder.decode(value).trim();
                    const lines = chunk.split('\n');
                    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            const data = line.replace('data: ', '').trim();
                            if (data === '[DONE]') continue;
                            
                            try {
                                const parsed = JSON.parse(data);
                                if (parsed.content) {
                                    tempResponse += parsed.content;
                                    setResponse(tempResponse); // Show raw text during streaming
                                } else if (parsed.error) {
                                    console.error('Error:', parsed.error);
                                    setResponse('Error: ' + parsed.error);
                                }
                            } catch (parseError) {
                                console.error('Error parsing chunk:', parseError);
                            }
                        }
                    }
                }
            }

            // Only convert to markdown after streaming is complete
            const formattedHtml = marked.parse(tempResponse);
            setFormattedResponse(formattedHtml);
            setResponse(tempResponse);
        } catch (error) {
            console.error('Error:', error);
            setResponse('Error: ' + error.message);
        } finally {
            setIsLoading(false);
        }
    };

    const getSimilarityColor = (similarity) => {
        const percentage = similarity * 100;
        if (percentage <= 55) return '#dc3545'; // red
        if (percentage <= 75) return '#fd7e14'; // orange
        return '#28a745'; // green
    };

    return (
        <div style={{ 
            padding: '20px',
            maxWidth: '800px',
            margin: '0 auto',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif'
        }}>
            <style>
                {`
                    @keyframes flash {
                        0% { background-color: #bbdefb; }
                        80% { background-color: #bbdefb; }
                        100% { background-color: transparent; }
                    }
                    .example-prompt {
                        padding: 6px 10px;
                        border: 1px solid #e1e8ed;
                        border-radius: 4px;
                        cursor: pointer;
                        transition: border-color 0.2s;
                        font-size: 13px;
                        color: #2c3e50;
                    }
                    .example-prompt:hover {
                        border-color: #90caf9;
                        background-color: #f8f9fa;
                    }
                    .example-prompt.clicked {
                        animation: flash 0.6s ease-in-out;
                    }
                    .markdown-content {
                        line-height: 1.2;
                    }
                    .markdown-content p {
                        margin: 0;
                    }
                    .markdown-content ol, 
                    .markdown-content ul {
                        margin: 0;
                        padding-left: 16px;
                    }
                    .markdown-content li {
                        margin: 0;
                        padding: 0;
                    }
                    .markdown-content li p {
                        margin: 0;
                    }
                    .markdown-content h1,
                    .markdown-content h2,
                    .markdown-content h3,
                    .markdown-content h4 {
                        margin: 4px 0 1px 0;
                    }
                    .markdown-content *:first-child {
                        margin-top: 0;
                    }
                    .markdown-content *:last-child {
                        margin-bottom: 0;
                    }
                `}
            </style>
            <h3 style={{ 
                color: '#2c3e50',
                marginBottom: '20px',
                fontWeight: '500'
            }}>EDED RAG Query</h3>
            <form onSubmit={handleQuerySubmit} style={{ marginBottom: '20px' }}>
                <div style={{ display: 'flex', marginBottom: '8px' }}>
                    <input
                        type="text"
                        value={query}
                        onChange={handleQueryChange}
                        placeholder="Query"
                        style={{ 
                            flex: 1,
                            marginRight: '10px',
                            padding: '8px 12px',
                            border: '1px solid #ddd',
                            borderRadius: '6px',
                            fontSize: '14px',
                            outline: 'none',
                            transition: 'border-color 0.2s, box-shadow 0.2s'
                        }}
                    />
                    <button 
                        type="submit" 
                        disabled={isLoading || !query.trim()}
                        style={{
                            padding: '8px 16px',
                            backgroundColor: query.trim() && !isLoading ? '#3498db' : '#95a5a6',
                            color: 'white',
                            border: 'none',
                            borderRadius: '6px',
                            cursor: query.trim() && !isLoading ? 'pointer' : 'not-allowed',
                            transition: 'background-color 0.2s',
                            fontSize: '14px',
                            fontWeight: '500'
                        }}
                    >
                        {isLoading ? 'Loading...' : 'Send'}
                    </button>
                </div>
            </form>

            <div style={{ marginTop: '20px' }}>
                
                <div style={{
                    whiteSpace: 'pre-wrap',
                    border: '1px solid #e1e8ed',
                    borderRadius: '8px',
                    padding: '15px',
                    backgroundColor: 'white',
                    fontSize: '14px',
                    lineHeight: '1.6',
                    color: '#2c3e50',
                    marginBottom: '15px'
                }}>
                    {isLoading ? (
                        <div>{response}</div>
                    ) : (
                        <div 
                            className="markdown-content"
                            dangerouslySetInnerHTML={{ __html: formattedResponse || '<span style="color: #9ca3af;">Response...</span>' }}
                        />
                    )}
                </div>

                {/* Example Queries */}
                <div style={{ marginBottom: '15px' }}>
                    <div
                        onClick={() => setShowExamples(!showExamples)}
                        style={{ 
                            fontSize: '11px',
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px',
                            color: '#6c757d',
                            marginBottom: '8px',
                            cursor: 'pointer',
                            display: 'flex',
                            alignItems: 'center',
                            userSelect: 'none'
                        }}
                    >
                        <span style={{
                            display: 'inline-block',
                            transform: showExamples ? 'rotate(90deg)' : 'rotate(0deg)',
                            transition: 'transform 0.2s',
                            marginRight: '4px'
                        }}>▶</span>
                        Example Queries
                    </div>
                    <div style={{
                        maxHeight: showExamples ? '500px' : '0',
                        overflow: 'hidden',
                        transition: 'max-height 0.3s ease-in-out',
                        display: showExamples ? 'block' : 'none'
                    }}>
                        <div style={{
                            display: 'grid',
                            gridTemplateColumns: '1fr 1fr',
                            gap: '10px',
                            marginBottom: '8px'
                        }}>
                            {examplePrompts.map((prompt, index) => (
                                <div
                                    key={index}
                                    className="example-prompt"
                                    onClick={() => handlePromptClick(prompt)}
                                >
                                    {prompt}
                                </div>
                            ))}
                        </div>
                        <div style={{
                            fontSize: '11px',
                            color: '#94a3b8',
                            marginTop: '8px',
                            fontStyle: 'italic'
                        }}>
                        </div>
                    </div>
                </div>

                {topKSimilarity !== null && (
                    <div style={{
                        padding: '10px',
                        backgroundColor: '#f8f9fa',
                        borderRadius: '6px',
                        fontSize: '14px',
                        color: '#343a40',
                        display: 'flex',
                        alignItems: 'center',
                        gap: '8px'
                    }}>
                        <div style={{
                            width: '12px',
                            height: '12px',
                            backgroundColor: getSimilarityColor(topKSimilarity),
                            borderRadius: '3px'
                        }}></div>
                        Top-K Similarity: {(topKSimilarity * 100).toFixed(1)}%
                    </div>
                )}
                <div style={{
                    marginBottom: '20px',
                    border: '1px solid #dee2e6',
                    borderRadius: '6px',
                    padding: '10px',
                    backgroundColor: '#f8f9fa',
                    fontSize: '14px',
                    color: '#495057'
                }}>
                    Context/Similarities:
                    <ul>
                        {similarities.map((sim, index) => (
                            <li key={index} style={{ marginBottom: '10px' }}>
                                <div
                                    dangerouslySetInnerHTML={{ __html: sim.context }}
                                    style={{ marginBottom: '5px' }}
                                />
                                <div style={{ 
                                    display: 'flex', 
                                    alignItems: 'center',
                                    gap: '8px',
                                    color: '#343a40'
                                }}>
                                    <div style={{
                                        width: '12px',
                                        height: '12px',
                                        backgroundColor: getSimilarityColor(sim.similarity),
                                        borderRadius: '3px'
                                    }}></div>
                                    Similarity: {(sim.similarity * 100).toFixed(1)}%
                                </div>
                            </li>
                        ))}
                    </ul>
                </div>

            </div>
        </div>
    );
}

export default App;