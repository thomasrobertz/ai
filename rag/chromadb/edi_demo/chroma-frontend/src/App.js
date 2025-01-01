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
            console.log('Sending query to backend:', query);

            const responseStream = await fetch('http://127.0.0.1:5000/query', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query }),
            });

            if (!responseStream.ok) {
                throw new Error(`HTTP error! status: ${responseStream.status}`);
            }

            console.log('Received response stream from backend');
            const reader = responseStream.body.getReader();
            const decoder = new TextDecoder();
            let done = false;

            while (!done) {
                const { value, done: streamDone } = await reader.read();
                done = streamDone;
                if (value) {
                    const chunk = decoder.decode(value).trim();

                    // Parse the JSON stream chunk
                    try {
                        const event = JSON.parse(chunk.replace('data: ', '').trim());
                        if (event.rag_context) {
                            console.log('Received RAG context:', event.rag_context);
                            setRagContext(event.rag_context);
                        } else if (event.openai_response) {
                            console.log('Received OpenAI response:', event.openai_response);
                            setResponse((prev) => prev + event.openai_response);
                        } else if (event.error) {
                            console.error('Error:', event.error);
                            setResponse('Error: ' + event.error);
                        }
                    } catch (parseError) {
                        console.error('Error parsing chunk:', parseError);
                    }
                } else {
                    console.warn('Received empty chunk or no data streamed.');
                }
            }

            console.log('Stream reading completed');
        } catch (error) {
            console.error('Error streaming response:', error);
            setResponse('Error: Unable to fetch the response. Please check the backend.');
        } finally {
            setIsLoading(false); // Reset loading state
        }
    };

    return (
        <div style={{ padding: '20px' }}>
            <h1>Chroma Query Interface</h1>
            <form onSubmit={handleQuerySubmit}>
                <input
                    type="text"
                    value={query}
                    onChange={handleQueryChange}
                    placeholder="Enter your query"
                    style={{ width: '300px', marginRight: '10px' }}
                />
                <button type="submit" disabled={isLoading}>
                    {isLoading ? 'Loading...' : 'Search'}
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
                        <strong>RAG Context:</strong> {ragContext}
                    </div>
                )}
            </div>
        </div>
    );
}

export default App;