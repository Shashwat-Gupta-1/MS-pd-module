import '../styles/globals.css';
import { CaseProvider } from '../lib/CaseContext';

export default function RootLayout({ children }: { children: React.ReactNode }) {
    return (
        <html lang="en">
            <body>
                <CaseProvider>{children}</CaseProvider>
            </body>
        </html>
    );
}
