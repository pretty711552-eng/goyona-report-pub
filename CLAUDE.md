# 고요나 프로젝트

## 서비스 정보
- **브랜드**: 고요나 (Goyona) - 스포츠 사운드 헤어밴드
- **메인 상품**: 고요나 블루이어 사운드 헤어밴드 (가격/원가는 환경변수 PRODUCT_PRICE / PRODUCT_COST 참조)
- **쇼핑몰**: 카페24 기반
  - 대표 도메인: goyonasport.com
  - 타기관 도메인: goyonaofficial.com
  - 카페24 기본: goyonaband.cafe24.com
- **대표**: 전상훈 (주식회사고요나)
- **사업자등록번호**: 8808603917
- **위치**: 경기도 남양주시 경춘로 460

## 연동된 서비스

### Google Analytics (GA4)
- 측정 ID: G-W0SK5SFEPE
- 속성 ID: 526888514
- 구글 광고 태그: AW-17989041512
- 토큰 파일: ga_token.json
- GA4 전자상거래 추적 코드가 카페24 head.html에 설치됨 (purchase, view_item, view_cart, begin_checkout)

### 카페24 API
- Client ID: Secrets로 관리
- mall_id: goyonaband
- 토큰 파일: cafe24_token.json
- 권한: mall.read_store, mall.read_order, mall.read_product, mall.read_salesreport

### 텔레그램 봇
- 봇: @goyona_report_bot
- 토큰: 텔레그램 봇 토큰은 secrets에 저장
- 채팅 ID: Secrets로 관리
- 1시간마다 자동 리포트 전송 (GitHub Actions)

### GitHub Actions
- 저장소: pretty711552-eng/goyona-report (비공개)
- 매 정각 자동 실행
- 리포트 내용: 매출, 원가, 순이익, 전환율, 트래픽, 채널별, 시간대별

## 현재 데이터 요약 (30일 기준)
- 방문자: ~15,800명
- 주문: ~100건
- 전환율: ~0.63%
- 주요 유입: 인스타 유료 광고 80%, 자연검색 4%
- 인스타 광고 이탈률: 51%
- 자연검색 참여율: 73% (최고 품질)
- 모바일 95%, 데스크톱 3%

## 광고 구조
- 메타(인스타/페이스북) 광고 → hairband.html (외부 랜딩) → 상품 페이지 → 결제
- hairband.html이 전환율 상승에 큰 기여

## 사이드 사업
- 대출나무 (loan-namu.com): 대출 고객 DB를 대출 업체에 판매하는 플랫폼
- partners.loan-namu.com: 협력사 관리 페이지

## 알려진 이슈
- 카카오 로그인: goyonasport.com 도메인 리다이렉트 URI 미등록 → 카페24 고객센터 문의 필요
- 메타 광고 API 미연결 (광고비 자동 집계 안 됨)
- 네이버/구글 검색 등록 필요

## 주의사항
- 한국어로만 대화할 것
- 영어 약어/전문용어 사용 금지
- 토큰 파일은 보안에 주의
