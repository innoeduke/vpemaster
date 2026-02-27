import click
from flask.cli import with_appcontext
from app.services.blockchain_service import BlockchainService

@click.command('deploy')
@with_appcontext
def deploy_contract():
    """Deploy the LevelTracker smart contract to Sepolia."""
    click.echo('Deploying LevelTracker contract...')
    try:
        contract_address = BlockchainService.deploy_contract()
        click.echo(f'\nSuccess! Contract deployed to: {contract_address}')
        click.echo(f'IMPORTANT: Update your .env file with:')
        click.echo(f'LEVEL_TRACKER_CONTRACT_ADDRESS={contract_address}\n')
    except Exception as e:
        click.echo(f"\nDeployment failed: {e}")
        exit(1)
@click.command('upload')
@with_appcontext
def upload_achievements():
    """Bulk upload level-completion achievements to Sepolia."""
    click.echo('Scanning database for level-completion achievements...')
    
    try:
        # We'll use the service to do the heavy lifting
        results = BlockchainService.bulk_upload()
        
        if not results:
            click.echo("No valid achievements found to upload.")
            return

        success_count = sum(1 for r in results if r['success'])
        total = len(results)
        
        click.echo("-" * 50)
        click.echo("Bulk upload complete!")
        click.echo(f"Successfully processed {success_count}/{total} records.")
        click.echo("(Achievements already on-chain were skipped efficiently.)")
                    
    except ValueError as e:
        click.echo(f"Error: {e}")
    except Exception as e:
        click.echo(f"An unexpected error occurred: {e}")
