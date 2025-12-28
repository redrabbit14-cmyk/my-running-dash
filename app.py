/* 크루원 카드 - 모바일용 간소화 */
    .crew-card {
        background: white;
        border: 2px solid #e5e7eb;
        border-radius: 8px;
        padding: 8px 4px;
        text-align: center;
        height: 100%;
        min-width: 0;
    }
    
    .crew-avatar {
        width: 50px;
        height: 50px;
        border-radius: 50%;
        background: linear-gradient(135deg, #3b82f6, #60a5fa);
        margin: 0 auto 6px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 24px;
        border: 2px solid white;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    
    .crew-stat-box {
        background: #f3f4f6;
        border-radius: 4px;
        padding: 4px 2px;
        margin: 2px 0;
        font-size: 10px;
    }
    
    /* 크루 컨테이너 */
    .crew-container {
        display: flex;
        gap: 6px;
        overflow-x: auto;
        -webkit-overflow-scrolling: touch;
    }
    
    .crew-container > div {
        flex: 1;
        min-width: 0;
    }
