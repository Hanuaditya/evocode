import './globals.css';
import BugReportWidget from './components/BugReportWidget';

export const metadata = {
  title: 'My Portfolio',
  description: 'Welcome to my portfolio website',
};

export default function RootLayout({ children }) {
  return (
    <html lang="en">
      <body className="bg-white dark:bg-gray-950 text-gray-900 dark:text-gray-100 min-h-screen font-sans">
        
        {/* Existing Layout / Portfolio Content */}
        {children}
        
        {/* EvoCode Global Floating Widget Injected Safely */}
        <BugReportWidget />
        
      </body>
    </html>
  );
}
