import React, { useState } from 'react';

function App() {
    const [query, setQuery] = useState('');
    const [response, setResponse] = useState('');
    const [ragContext, setRagContext] = useState(''); // New state for RAG context
    const [isLoading, setIsLoading] = useState(false);

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
        <div style={{ padding: '20px' }}>
            <h3>EDED RAG Query</h3>
            <form onSubmit={handleQuerySubmit}>
                <input
                    type="text"
                    value={query}
                    onChange={handleQueryChange}
                    placeholder="Query"
                    style={{ width: '300px', marginRight: '10px' }}
                />
                <button 
                    type="submit" 
                    disabled={isLoading || !query.trim()}
                    style={{
                        padding: '5px 15px',
                        cursor: query.trim() && !isLoading ? 'pointer' : 'not-allowed',
                        opacity: query.trim() && !isLoading ? 1 : 0.6
                    }}
                >
                    {isLoading ? 'Loading...' : 'Send'}
                </button>
            </form>
            <div style={{ marginTop: '20px' }}>
                <h2>Response:</h2>
                <div style={{ whiteSpace: 'pre-wrap', border: '1px solid #ddd', padding: '10px' }}>
                    {response}
                </div>
                {ragContext && (
                    <div
                        style={{
                            marginTop: '10px',
                            padding: '10px',
                            border: '1px solid #ccc',
                            backgroundColor: '#f9f9f9',
                            fontSize: '12px',
                            color: '#555',
                        }}
                    >
                        <strong>RAG Context:</strong>{' '}
                        <span dangerouslySetInnerHTML={{ __html: ragContext }} />
                    </div>
                )}
            </div>
        </div>
    );
}

export default App;