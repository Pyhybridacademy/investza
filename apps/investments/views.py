"""
investments/views.py
Investment listing, creation, and management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from .models import InvestmentCategory, InvestmentPlan, Investment
from .forms import CreateInvestmentForm


@login_required
def investment_list(request):
    """Show all investment categories and plans."""
    categories = InvestmentCategory.objects.filter(is_active=True).prefetch_related(
        'plans'
    )
    user_investments = Investment.objects.filter(
        user=request.user
    ).select_related('plan__category').order_by('-created_at')[:5]

    context = {
        'categories': categories,
        'user_investments': user_investments,
    }
    return render(request, 'investments/list.html', context)


@login_required
def investment_detail(request, pk):
    """Detail view for a single investment."""
    investment = get_object_or_404(Investment, pk=pk, user=request.user)
    return render(request, 'investments/detail.html', {'investment': investment})


@login_required
def create_investment(request, plan_id=None):
    """Create a new investment."""
    wallet = request.user.get_wallet()

    initial = {}
    if plan_id:
        plan = get_object_or_404(InvestmentPlan, pk=plan_id, is_active=True)
        initial['plan'] = plan

    if request.method == 'POST':
        form = CreateInvestmentForm(user=request.user, data=request.POST)
        if form.is_valid():
            investment = form.save(commit=False)
            investment.user = request.user
            investment.expected_roi = investment.plan.calculate_roi(investment.amount_invested)
            investment.expected_total = investment.plan.calculate_total_return(investment.amount_invested)
            investment.save()

            # Deduct from wallet
            wallet.debit(
                investment.amount_invested,
                f"Investment in {investment.plan.name} - Ref: {investment.reference}"
            )
            # Move to invested balance
            wallet.invested_balance += investment.amount_invested
            wallet.save(update_fields=['invested_balance'])

            # Activate investment
            investment.activate()

            messages.success(
                request,
                f"Investment of R{investment.amount_invested:,.2f} in {investment.plan.name} has been activated!"
            )
            return redirect('investment_detail', pk=investment.pk)
    else:
        form = CreateInvestmentForm(user=request.user, initial=initial)

    categories = InvestmentCategory.objects.filter(is_active=True).prefetch_related('plans')

    return render(request, 'investments/create.html', {
        'form': form,
        'wallet': wallet,
        'categories': categories,
    })


@login_required
def my_investments(request):
    """All user investments."""
    investments = Investment.objects.filter(
        user=request.user
    ).select_related('plan__category').order_by('-created_at')

    active = investments.filter(status='ACTIVE')
    matured = investments.filter(status='MATURED')
    all_investments = investments

    context = {
        'active_investments': active,
        'matured_investments': matured,
        'all_investments': all_investments,
    }
    return render(request, 'investments/my_investments.html', context)


@require_GET
def get_plan_details(request, plan_id):
    """AJAX endpoint to get plan ROI details."""
    try:
        plan = InvestmentPlan.objects.get(pk=plan_id, is_active=True)
        amount = float(request.GET.get('amount', 0))
        roi = float(plan.calculate_roi(amount))
        total = float(plan.calculate_total_return(amount))
        return JsonResponse({
            'success': True,
            'plan_name': plan.name,
            'roi_percentage': float(plan.roi_percentage),
            'duration': f"{plan.duration_value} {plan.get_duration_unit_display()}",
            'duration_days': plan.duration_in_days,
            'minimum_amount': float(plan.minimum_amount),
            'maximum_amount': float(plan.maximum_amount),
            'expected_roi': roi,
            'expected_total': total,
            'returns_principal': plan.returns_principal,
        })
    except InvestmentPlan.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Plan not found'}, status=404)
