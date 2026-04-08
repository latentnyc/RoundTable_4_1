import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
    children: ReactNode;
    /** Label shown in the error UI (e.g. "Battlemap", "Chat") */
    label?: string;
}

interface State {
    hasError: boolean;
    error: Error | null;
    errorInfo: ErrorInfo | null;
}

export default class ErrorBoundary extends Component<Props, State> {
    public state: State = {
        hasError: false,
        error: null,
        errorInfo: null
    };

    public static getDerivedStateFromError(error: Error): Partial<State> {
        return { hasError: true, error };
    }

    public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
        console.error("Uncaught error:", error, errorInfo);
        this.setState({ errorInfo });
    }

    private handleReset = () => {
        this.setState({ hasError: false, error: null, errorInfo: null });
    };

    private handleReload = () => {
        window.location.reload();
    };

    public render() {
        if (this.state.hasError) {
            const label = this.props.label || 'This section';
            return (
                <div className="p-4 bg-red-900/20 border border-red-500/50 rounded-lg text-red-200 m-4 flex flex-col gap-3">
                    <h2 className="text-xl font-bold">{label} crashed.</h2>
                    <p className="text-sm text-red-300/80">
                        An unexpected error occurred. You can try recovering or reload the page.
                    </p>
                    <div className="flex gap-2">
                        <button
                            onClick={this.handleReset}
                            className="px-3 py-1.5 text-sm bg-red-800/50 hover:bg-red-700/50 rounded-md transition-colors"
                        >
                            Try Again
                        </button>
                        <button
                            onClick={this.handleReload}
                            className="px-3 py-1.5 text-sm bg-neutral-800 hover:bg-neutral-700 rounded-md transition-colors"
                        >
                            Reload Page
                        </button>
                    </div>
                    <details className="whitespace-pre-wrap font-mono text-xs text-red-400/60 mt-2">
                        <summary className="cursor-pointer text-red-300/50">Error details</summary>
                        {this.state.error && this.state.error.toString()}
                        <br />
                        {this.state.errorInfo && this.state.errorInfo.componentStack}
                    </details>
                </div>
            );
        }

        return this.props.children;
    }
}
