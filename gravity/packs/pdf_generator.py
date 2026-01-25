"""
PDF Generator using WeasyPrint
Generates professional PDF reports from pack data
"""

from typing import Dict, Any
import logging
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, Template
from datetime import datetime

logger = logging.getLogger(__name__)


class PDFGenerator:
    """
    Generates PDF Negotiation Packs using WeasyPrint
    """
    
    def __init__(self):
        """Initialize PDF generator"""
        # Set up Jinja2 template environment
        template_dir = Path(__file__).parent / 'templates'
        template_dir.mkdir(parents=True, exist_ok=True)
        
        self.env = Environment(loader=FileSystemLoader(str(template_dir)))
        self.env.filters['currency'] = self._currency_filter
        self.env.filters['percent'] = self._percent_filter
        
        logger.info("PDF generator initialized")
    
    def generate_pdf(
        self,
        pack_data: Dict[str, Any],
        output_path: str
    ) -> str:
        """
        Generate PDF from pack data
        
        Args:
            pack_data: Complete pack data dict
            output_path: Output file path
        
        Returns:
            Path to created PDF file
        """
        logger.info(f"Generating PDF: {output_path}")
        
        # Render HTML from template
        html_content = self._render_html(pack_data)
        
        # Convert HTML to PDF using WeasyPrint
        try:
            from weasyprint import HTML, CSS
            
            # Create output directory
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Generate PDF
            HTML(string=html_content).write_pdf(
                output_path,
                stylesheets=[self._get_css()]
            )
            
            logger.info(f"PDF generated successfully: {output_path}")
            return str(output_file.absolute())
            
        except ImportError:
            logger.error("WeasyPrint not installed. Install with: pip install weasyprint")
            # Fallback: save HTML instead
            html_path = output_path.replace('.pdf', '.html')
            with open(html_path, 'w') as f:
                f.write(html_content)
            logger.info(f"Saved as HTML instead: {html_path}")
            return html_path
    
    def _render_html(self, pack_data: Dict[str, Any]) -> str:
        """Render HTML from template"""
        try:
            template = self.env.get_template('pack_template.html')
        except:
            # Use inline template if file doesn't exist
            template = Template(self._get_default_template())
        
        return template.render(**pack_data)
    
    def _get_css(self) -> 'CSS':
        """Get CSS stylesheet"""
        from weasyprint import CSS
        
        css_path = Path(__file__).parent / 'templates' / 'pack_styles.css'
        if css_path.exists():
            return CSS(filename=str(css_path))
        else:
            return CSS(string=self._get_default_css())
    
    def _currency_filter(self, value) -> str:
        """Format currency"""
        if value is None:
            return "N/A"
        try:
            return f"${float(value):,.0f}"
        except:
            return str(value)
    
    def _percent_filter(self, value) -> str:
        """Format percentage"""
        if value is None:
            return "N/A"
        try:
            return f"{float(value):.1f}%"
        except:
            return str(value)
    
    def _get_default_template(self) -> str:
        """Default HTML template"""
        return """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>NIL Negotiation Pack</title>
</head>
<body>
    <div class="cover-page">
        <h1>Annual NIL Negotiation Pack</h1>
        <h2>{{ athlete.name }}</h2>
        <p>{{ athlete.school }} | {{ athlete.position }}</p>
        <p>Generated: {{ generated_at }}</p>
    </div>
    
    <div class="executive-summary">
        <h2>Executive Summary</h2>
        <div class="key-metrics">
            <div class="metric">
                <span class="label">Gravity Score</span>
                <span class="value">{{ gravity_score.gravity_conf|round(1) }}/100</span>
            </div>
            <div class="metric">
                <span class="label">IACV (P50)</span>
                <span class="value">{{ valuation.iacv_p50|currency }}</span>
            </div>
            <div class="metric">
                <span class="label">Value Range</span>
                <span class="value">{{ valuation.iacv_p25|currency }} - {{ valuation.iacv_p75|currency }}</span>
            </div>
        </div>
    </div>
    
    <div class="component-breakdown">
        <h2>Gravity Component Breakdown</h2>
        <table>
            <thead>
                <tr><th>Component</th><th>Score</th><th>Confidence</th></tr>
            </thead>
            <tbody>
                {% for name, data in gravity_score.components.items() %}
                <tr>
                    <td>{{ name|title }}</td>
                    <td>{{ data.score|round(1) }}</td>
                    <td>{{ (data.confidence * 100)|round(1) }}%</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    
    <div class="nil-portfolio">
        <h2>Current NIL Portfolio</h2>
        <p>Total Deals: {{ nil_portfolio.total_deals }}</p>
        <p>Latest Valuation: {{ nil_portfolio.latest_valuation|currency }}</p>
        
        <h3>Recent Deals</h3>
        <table>
            <thead>
                <tr><th>Brand</th><th>Type</th><th>Value</th><th>Verified</th></tr>
            </thead>
            <tbody>
                {% for deal in nil_portfolio.deals[:10] %}
                <tr>
                    <td>{{ deal.brand }}</td>
                    <td>{{ deal.type }}</td>
                    <td>{{ deal.value|currency }}</td>
                    <td>{{ "Yes" if deal.is_verified else "No" }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
    </div>
    
    {% if underwriting %}
    <div class="deal-underwriting">
        <h2>Deal Underwriting</h2>
        <div class="decision {{ underwriting.decision }}">
            <h3>Decision: {{ underwriting.decision|upper }}</h3>
            <p>{{ underwriting.decision_rationale }}</p>
        </div>
        
        <h3>Negotiation Strategy</h3>
        <table>
            <tr><th>Anchor</th><td>{{ negotiation.anchor_price|currency }}</td></tr>
            <tr><th>Target</th><td>{{ negotiation.target_price|currency }}</td></tr>
            <tr><th>Walk-Away</th><td>{{ negotiation.walk_away_price|currency }}</td></tr>
        </table>
        
        <h4>Recommended Clauses</h4>
        <ul>
            {% for clause in negotiation.recommended_clauses %}
            <li>{{ clause }}</li>
            {% endfor %}
        </ul>
    </div>
    {% endif %}
    
    <div class="footer">
        <p>Generated by Gravity NIL Underwriting System</p>
        <p>{{ generated_at }}</p>
    </div>
</body>
</html>
"""
    
    def _get_default_css(self) -> str:
        """Default CSS styling"""
        return """
@page {
    size: Letter;
    margin: 1in;
}

body {
    font-family: 'Helvetica', 'Arial', sans-serif;
    color: #333;
    line-height: 1.6;
}

.cover-page {
    text-align: center;
    padding: 100px 0;
    page-break-after: always;
}

.cover-page h1 {
    font-size: 36px;
    margin-bottom: 20px;
}

.cover-page h2 {
    font-size: 28px;
    color: #0066cc;
}

.executive-summary {
    margin: 40px 0;
}

.key-metrics {
    display: flex;
    justify-content: space-around;
    margin: 30px 0;
}

.metric {
    text-align: center;
}

.metric .label {
    display: block;
    font-size: 14px;
    color: #666;
    margin-bottom: 10px;
}

.metric .value {
    display: block;
    font-size: 24px;
    font-weight: bold;
    color: #0066cc;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 20px 0;
}

table th, table td {
    padding: 12px;
    text-align: left;
    border-bottom: 1px solid #ddd;
}

table th {
    background-color: #f5f5f5;
    font-weight: bold;
}

.decision {
    padding: 20px;
    border-radius: 5px;
    margin: 20px 0;
}

.decision.approve {
    background-color: #d4edda;
    border-left: 4px solid #28a745;
}

.decision.counter {
    background-color: #fff3cd;
    border-left: 4px solid #ffc107;
}

.decision.no-go {
    background-color: #f8d7da;
    border-left: 4px solid #dc3545;
}

.footer {
    margin-top: 50px;
    text-align: center;
    font-size: 12px;
    color: #666;
}
"""


def generate_pack_pdf(pack_data: Dict[str, Any], output_path: str) -> str:
    """
    Generate pack PDF
    
    Args:
        pack_data: Pack data dict
        output_path: Output file path
    
    Returns:
        Path to created PDF
    """
    generator = PDFGenerator()
    return generator.generate_pdf(pack_data, output_path)
