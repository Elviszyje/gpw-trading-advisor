#!/usr/bin/env python
"""
Monitor schedulera scraperów - sprawdza czy automatyczne uruchamianie działa poprawnie
"""
import sys
import os
import django
import time
from datetime import timedelta

# Setup Django
sys.path.append('.')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gpw_advisor.settings')
django.setup()

from apps.core.models import ScrapingSchedule, ScrapingExecution
from django.utils import timezone

def check_scheduler_status():
    """Sprawdź status schedulera i wyświetl informacje"""
    print("=" * 60)
    print(f"📊 MONITOR SCHEDULERA - {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # Sprawdź procesy Celery
    import subprocess
    try:
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        celery_processes = [line for line in result.stdout.split('\n') if 'celery' in line and 'gpw_advisor' in line]
        
        worker_count = len([p for p in celery_processes if 'worker' in p])
        beat_count = len([p for p in celery_processes if 'beat' in p])
        
        print(f"🔧 Celery Worker: {worker_count} procesów")
        print(f"⏰ Celery Beat: {beat_count} procesów")
        
        if worker_count == 0:
            print("❌ UWAGA: Brak Celery Worker! Uruchom: celery -A gpw_advisor worker --detach")
        if beat_count == 0:
            print("❌ UWAGA: Brak Celery Beat! Uruchom: celery -A gpw_advisor beat --detach")
            
    except Exception as e:
        print(f"❌ Błąd sprawdzania procesów: {e}")
    
    print()
    
    # Sprawdź active schedules
    schedules = ScrapingSchedule.objects.filter(is_active=True)
    now = timezone.now()
    
    print(f"📋 AKTYWNE SCHEDULERY ({schedules.count()}):")
    print("-" * 40)
    
    due_count = 0
    for schedule in schedules:
        should_run = schedule.should_run_now()
        if should_run:
            due_count += 1
            
        status_icon = "🔥" if should_run else "⏳"
        
        # Oblicz czas do następnego uruchomienia
        next_run_info = ""
        if schedule.last_run and not should_run:
            time_since = now - schedule.last_run
            
            if schedule.frequency_unit == 'minutes':
                interval = timedelta(minutes=schedule.frequency_value)
            elif schedule.frequency_unit == 'hours':
                interval = timedelta(hours=schedule.frequency_value)
            elif schedule.frequency_unit == 'days':
                interval = timedelta(days=schedule.frequency_value)
            else:
                interval = timedelta(seconds=schedule.frequency_value)
                
            remaining = interval - time_since
            if remaining.total_seconds() > 0:
                remaining_minutes = int(remaining.total_seconds() // 60)
                remaining_seconds = int(remaining.total_seconds() % 60)
                next_run_info = f" (za {remaining_minutes}m {remaining_seconds}s)"
        
        print(f"{status_icon} {schedule.name}{next_run_info}")
        print(f"    Typ: {schedule.scraper_type} | Częstotliwość: {schedule.frequency_value} {schedule.frequency_unit}")
        
        if schedule.last_run:
            last_run_str = schedule.last_run.strftime('%H:%M:%S')
            time_ago = now - schedule.last_run
            if time_ago.days > 0:
                time_ago_str = f"{time_ago.days}d {time_ago.seconds//3600}h"
            elif time_ago.seconds > 3600:
                time_ago_str = f"{time_ago.seconds//3600}h {(time_ago.seconds%3600)//60}m"
            else:
                time_ago_str = f"{time_ago.seconds//60}m {time_ago.seconds%60}s"
            print(f"    Ostatnie: {last_run_str} ({time_ago_str} temu)")
        else:
            print(f"    Ostatnie: nigdy")
        print()
    
    print(f"🎯 PODSUMOWANIE: {due_count} scraperów wymaga uruchomienia")
    
    # Sprawdź ostatnie wykonania
    print("\n" + "=" * 40)
    print("📈 OSTATNIE WYKONANIA (5 najnowszych):")
    print("-" * 40)
    
    recent = ScrapingExecution.objects.order_by('-started_at')[:5]
    for execution in recent:
        status_icon = "✅" if execution.success else "❌"
        duration = ""
        if execution.completed_at:
            duration = f" ({execution.completed_at - execution.started_at})"
        
        start_time = execution.started_at.strftime('%H:%M:%S')
        print(f"{status_icon} {execution.schedule.name} - {start_time}{duration}")
        
        if execution.error_message:
            print(f"    Błąd: {execution.error_message[:80]}...")
        if execution.items_processed > 0:
            print(f"    Przetworzono: {execution.items_processed} elementów")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--watch":
        print("📺 Tryb ciągłego monitorowania (Ctrl+C aby zakończyć)")
        print("Odświeżanie co 30 sekund...\n")
        
        try:
            while True:
                check_scheduler_status()
                print("💤 Czekam 30 sekund...\n")
                time.sleep(30)
        except KeyboardInterrupt:
            print("\n👋 Monitoring zakończony")
    else:
        check_scheduler_status()
        print("💡 Użyj --watch dla ciągłego monitorowania")
