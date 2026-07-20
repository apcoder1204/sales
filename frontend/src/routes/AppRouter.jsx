import React, { lazy, Suspense } from 'react'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider } from '@context/AuthContext'
import { ToastProvider } from '@context/ToastContext'
import { BranchProvider } from '@context/BranchContext'
import { CartProvider } from '@context/CartContext'
import { LanguageProvider } from '@context/LanguageContext'
import { useLanguage } from '@hooks/useLanguage'
import ProtectedRoute from './ProtectedRoute'
import RoleRoute from './RoleRoute'
import Spinner from '@components/feedback/Spinner'

const LoginPage = lazy(() => import('@features/auth/LoginPage'))
const ForgotPasswordPage = lazy(() => import('@features/auth/ForgotPasswordPage'))
const ResetPasswordPage = lazy(() => import('@features/auth/ResetPasswordPage'))
const AppShell = lazy(() => import('@components/layout/AppShell'))
const DashboardPage = lazy(() => import('@features/dashboard/DashboardPage'))
const ProductsPage = lazy(() => import('@features/products/ProductsPage'))
const CategoryPage = lazy(() => import('@features/products/CategoryPage'))
const StockAdjustPage = lazy(() => import('@features/products/StockAdjustPage'))
const MovementsPage = lazy(() => import('@features/inventory/MovementsPage'))
const PosPage = lazy(() => import('@features/pos/PosPage'))
const TransfersPage = lazy(() => import('@features/transfers/TransfersPage'))
const ReportsPage = lazy(() => import('@features/reports/ReportsPage'))
const ClosingPage = lazy(() => import('@features/closing/ClosingPage'))
const AuditPage = lazy(() => import('@features/audit/AuditPage'))
const UsersPage = lazy(() => import('@features/users/UsersPage'))

const Fallback = () => (
  <div className="flex items-center justify-center h-screen bg-bg">
    <Spinner size="lg" />
  </div>
)

// All feature components read UI strings from the shared, mutable `SW`
// object (see @constants/sw) rather than a reactive hook — so a language
// change can't just re-render in place, it needs the whole routed subtree to
// remount and re-read the now-updated strings. Keying on `language` (from
// LanguageProvider, which sits above this and so is unaffected by the
// remount) does exactly that without touching AuthProvider/CartProvider state.
function RoutedApp() {
  const { language } = useLanguage()
  return (
    <Suspense key={language} fallback={<Fallback />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/forgot-password" element={<ForgotPasswordPage />} />
        <Route path="/reset-password" element={<ResetPasswordPage />} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route index element={<Navigate to="/dashibodi" replace />} />
            <Route path="/dashibodi" element={<DashboardPage />} />

            <Route path="/bidhaa" element={
              <RoleRoute permissions={['products.read']}>
                <ProductsPage />
              </RoleRoute>
            } />
            <Route path="/bidhaa/jamii" element={
              <RoleRoute permissions={['products.read']}>
                <CategoryPage />
              </RoleRoute>
            } />
            <Route path="/bidhaa/marekebisho" element={
              <RoleRoute permissions={['inventory.read']}>
                <StockAdjustPage />
              </RoleRoute>
            } />

            <Route path="/hifadhi" element={<Navigate to="/bidhaa" replace />} />
            <Route path="/hifadhi/harakati" element={
              <RoleRoute permissions={['inventory.read']}>
                <MovementsPage />
              </RoleRoute>
            } />

            <Route path="/mauzo" element={
              <RoleRoute permissions={['sales.create']}>
                <PosPage />
              </RoleRoute>
            } />

            <Route path="/uhamisho" element={
              <RoleRoute permissions={['transfers.read']}>
                <TransfersPage />
              </RoleRoute>
            } />

            <Route path="/ripoti" element={
              <RoleRoute permissions={['reports.sales', 'reports.inventory', 'reports.closing']} any>
                <ReportsPage />
              </RoleRoute>
            } />

            <Route path="/ufungaji" element={
              <RoleRoute permissions={['closing.view']}>
                <ClosingPage />
              </RoleRoute>
            } />

            <Route path="/kumbukumbu" element={
              <RoleRoute permissions={['audit.read']}>
                <AuditPage />
              </RoleRoute>
            } />

            <Route path="/watumiaji" element={
              <RoleRoute permissions={['users.read']}>
                <UsersPage />
              </RoleRoute>
            } />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/dashibodi" replace />} />
      </Routes>
    </Suspense>
  )
}

export default function AppRouter() {
  return (
    <BrowserRouter>
      <LanguageProvider>
        <AuthProvider>
          <ToastProvider>
            <BranchProvider>
              <CartProvider>
                <RoutedApp />
              </CartProvider>
            </BranchProvider>
          </ToastProvider>
        </AuthProvider>
      </LanguageProvider>
    </BrowserRouter>
  )
}
