import React, { useState } from 'react';

function App() {
    const [query, setQuery] = useState('');
    const [response, setResponse] = useState('');
    const [ragContext, setRagContext] = useState('');
    const [isLoading, setIsLoading] = useState(false);
    const [showExamples, setShowExamples] = useState(true);

    const examplePrompts = [
        "Tell me about the element with code 1001.",
        "Show me all elements related to dates.",
        "Explain the usage of code 7431.", // Not working (perhaps add usage to text and or implement usage just like "code")
        "What does an..7 mean?",
        "List 4 elements with numeric representation.",
        "What elements are used for identification?",
        "Show me elements with code pattern 34..", // Not working
        "Which elements use alphanumeric format?",
        "Explain the difference between n2 and n..2",
        "What are conditional elements? *",
        "Which element has the description containing 'specify' and 'level'?",
        "What would be the representation for 'up to 20 numeric characters'?"
    ];

    const handlePromptClick = (prompt) => {
        setQuery(prompt);
    };

    const handleQueryChange = (e) => {
        setQuery(e.target.value);
    };

    const handleQuerySubmit = async (e) => {
        e.preventDefault();
        setResponse(''); // Clear previous response
        setRagContext(''); // Clear previous RAG context
        setIsLoading(true); // Set loading state

        try {
            // First, get the RAG context
            const contextResponse = await fetch('http://localhost:5000/context', {
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
            setRagContext(contextData.context);

            // Then, start streaming the OpenAI response
            const responseStream = await fetch('http://localhost:5000/query', {
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
                                    setResponse(prev => prev + parsed.content);
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
        } catch (error) {
            console.error('Error:', error);
            setResponse('Error: ' + error.message);
        } finally {
            setIsLoading(false);
        }
    };

    return (
        <div style={{ 
            padding: '20px',
            maxWidth: '800px',
            margin: '0 auto',
            fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Arial, sans-serif'
        }}>
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
                            transition: 'border-color 0.2s, box-shadow 0.2s',
                            ':focus': {
                                borderColor: '#3498db',
                                boxShadow: '0 0 0 3px rgba(52, 152, 219, 0.1)'
                            }
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
                <div style={{
                    fontSize: '11px',
                    color: '#94a3b8',
                    fontStyle: 'italic'
                }}>
                    At this time we fetch a maximum of 10 context records.
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
                    {response || 'Response will appear here...'}
                </div>
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
                    }}>
                        <div style={{
                            display: 'grid',
                            gridTemplateColumns: '1fr 1fr',
                            gap: '10px',
                            marginBottom: showExamples ? '8px' : '0'
                        }}>
                            {examplePrompts.map((prompt, index) => (
                                <div
                                    key={index}
                                    onClick={() => handlePromptClick(prompt)}
                                    style={{
                                        padding: '8px 12px',
                                        border: '1px solid #bfdbfe',
                                        borderRadius: '6px',
                                        backgroundColor: 'white',
                                        fontSize: '13px',
                                        color: '#3b82f6',
                                        cursor: 'pointer',
                                        transition: 'all 0.2s',
                                        ':hover': {
                                            backgroundColor: '#f0f9ff',
                                            borderColor: '#93c5fd'
                                        }
                                    }}
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
                            * This query will bypass context retrieval
                        </div>
                    </div>
                </div>
                {ragContext && (
                    <div
                        style={{
                            padding: '12px',
                            border: '1px solid #dee2e6',
                            borderRadius: '6px',
                            backgroundColor: '#f8f9fa',
                            fontSize: '12px',
                            color: '#6c757d',
                            lineHeight: '1.4'
                        }}
                    >
                        <div style={{ 
                            fontWeight: '500',
                            marginBottom: '6px',
                            fontSize: '11px',
                            textTransform: 'uppercase',
                            letterSpacing: '0.5px'
                        }}>Context</div>
                        <span dangerouslySetInnerHTML={{ __html: ragContext }} />
                    </div>
                )}
            </div>
        </div>
    );
}

export default App;